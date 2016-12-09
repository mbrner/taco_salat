#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd
from component import BaseComponent


class BaseLayer(object):
    def __init__(self, name, comment=''):
        self.name = name
        self.comment = comment
        self.component_dict = {}
        self.n_components = 0

    def add_component(self, component):
        assert component.name not in self.component_dict.keys(), \
            '{} already in layer {}'.format(name, self.name)
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
    def fit_df(self, df):
        new_df = None
        for key, component in self.component_dict.items():
            if hasattr(component, 'fit_df'):
                comp_df = component.fit_df(df)
                if new_df is None:
                    new_df = comp_df
                else:
                    new_df = new_df.join(comp_df)
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