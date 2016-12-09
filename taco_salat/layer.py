#!/usr/bin/env python
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor, wait

import pandas as pd
import numpy as np

from component import BaseComponent


class BaseLayer(object):
    def __init__(self, name, comment=''):
        self.name = name
        self.comment = comment
        self.component_dict = {}
        self.n_components = 0

    def add_component(self, component):
        assert component.name not in self.component_dict.keys(), \
            '{} already in layer {}'.format(component.name, self.name)
        self.n_components += 1
        self.component_dict[component.name] = component
        return self.component_dict[component.name]

    def get_component(self, name):
        return self.component_dict[name]

    def __getitem__(self, name):
        return self.get_component(name)

    def rename_component(self, component, new_name):
        if not isinstance(component, BaseComponent):
            component = self.get_component(component)
        old_name = component.name
        self.component_dict[new_name] = self.component_dict[old_name]
        del self.component_dict[old_name]
        component.name = new_name
        return old_name


class Layer(BaseLayer):
    def fit_df(self, df, kfold, final_model=False):
        new_df = pd.DataFrame()
        for train, test in kfold.split(np.empty(df.shape)):
            df_train = df.loc[train, :]
            df_test = df.loc[test, :]
            for key, component in self.component_dict.items():
                has_fit = hasattr(component, 'fit_df')
                has_predict = hasattr(component, 'predict_df')
                if has_fit and has_predict:
                    component.fit_df(df_train)
                    comp_df = component.predict_df(df_test)
                    new_df = new_df.join(comp_df)
        if final_model:
            for key, component in self.component_dict.items():
                if hasattr(component, 'fit_df'):
                    component = component.fit_df(df)
                    self.component_dict[component.name] = component
        return new_df

    def predict_df(self, df):
        new_df = None
        for key, component in self.component_dict.items():
            if hasattr(component, 'predict_df'):
                comp_df = component.predict_df(df)
                if new_df is None:
                    new_df = comp_df
                else:
                    new_df = new_df.join(comp_df)
        return new_df


class LayerParallel(Layer):
    def __init__(self,
                 name,
                 n_jobs,
                 predict_parallel=False,
                 fit_parallel=True,
                 comment=''):
        super(LayerParallel, self).__init__(name=name,
                                            comment=comment)
        self.n_jobs = n_jobs
        self.fit_parallel = fit_parallel
        self.predict_parallel = predict_parallel

    def fit_df(self, df, kfold, final_model=False):
        if self.fit_parallel:
            new_df = pd.DataFrame()

            def fit_predict_single_component(component, df_train, df_test):
                component = component.fit_df(df_train)
                return component, component.predict_df(df_test)

            with ThreadPoolExecutor(max_workers=self.n_jobs) as executor:
                futures = []
                for train, test in kfold.split(np.empty(df.shape)):
                    df_train = df.loc[train, :]
                    df_test = df.loc[test, :]
                    for key, component in self.component_dict.items():
                        has_fit = hasattr(component, 'fit_df')
                        has_predict = hasattr(component, 'predict_df')
                        if has_fit and has_predict:
                            sel_att = component.attributes
                            sel_att.append(component.label)
                            if component.weight is not None:
                                sel_att.append(component.weight)
                            futures.append(executor.submit(
                                fit_predict_single_component,
                                component=component,
                                df_train=df_train.loc[:, sel_att],
                                df_test=df_test.loc[:, sel_att]))
                results = wait(futures)
            for i, future_i in enumerate(results.done):
                component, comp_df = future_i.result()
                self.component_dict[component.name] = component
                new_df = new_df.join(comp_df)
            if final_model:
                with ThreadPoolExecutor(max_workers=self.n_jobs) as executor:
                    for key, component in self.component_dict.items():
                        has_fit = hasattr(component, 'fit_df')
                        has_predict = hasattr(component, 'predict_df')
                        if has_fit and has_predict:
                            sel_att = component.attributes
                            sel_att.append(component.label)
                            if component.weight is not None:
                                sel_att.append(component.weight)
                            component.fit_df(df.loc[:, sel_att])
                    results = wait(futures)
                for i, future_i in enumerate(results.done):
                    component = future_i.result()
                    self.component_dict[component.name] = component
        else:
            new_df = super(LayerParallel, self).fit_df(df,
                                                       kfold=kfold,
                                                       final_model=final_model)
        return new_df

    def predict_df(self, df):
        if self.predict_parallel:
            new_df = pd.DataFrame()
            with ThreadPoolExecutor(max_workers=self.n_jobs) as executor:
                futures = []
                for key, component in self.predict_df.items():
                    if hasattr(component, 'predict_df'):
                        sel_att = component.attributes
                        sel_att.append(component.label)
                        if component.weight is not None:
                            sel_att.append(component.weight)
                        futures.append(executor.submit(component.predict_df,
                                                       df=df.loc[:, sel_att]))
                results = wait(futures)
            for i, future_i in enumerate(results.done):
                comp_df = future_i.result()
                new_df = new_df.join(comp_df)
        else:
            new_df = super(LayerParallel, self).predict_df(df)
        return new_df
