#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, division
from copy import deepcopy

import numpy as np
from . import criteria
from .curve import CurveSliding, Curve


class ConfidenceCutter(object):
    """Method to find a confidence (X_c) cut curve depended on a second
    observable (X_o).

    Parameters
    ----------
    window_size: float
        Size of the sliding window

    n_steps : integer, optional (default=1000)
        Number of steps for the sliding window

    n_bootstraps : integer (default=3)
        Number of bootstraps. The curve is determined on n_boostraps
        samples and averaged.

    criteria : callable, optional (default=purity_criteria(threshold=0.99))
        Funtion criteria(y_true, y_pred, position, sample_weights=None)
        return True/False if the criteria is fulfilled.
        See e.g. purity_criteria

    positions : 1d array-lke, optional (default=None)
        If no positions are provided n_steps equally distributed between
        X_o min/max are used. The positions are mainly used for energy
        dependent decision functions

    conf_index : integer, optional (default=0)
        Index of the confidence in the X [n_samples, 2] used in all
        the functions. Default: X_c = X[:, 0] & X_o[:, 0]

    n_jobs : int, optinal (default=0)
        Max number of jobs used for the bootstrap loop.

    curve_file : str, optional (default=None)
        File from which a fitted cut curve should be loaded.

    random_state: None, int or RandomState
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by np.random.

    Attributes
    ----------
    cut_opts : Object CutOpts
        Container object containing all the options regarding the
        liding window

    criteria : callable
        See Parameters criteria

    conf_index : int or list
        See Parameters conf_index

    n_jobs : int
        Max number of jobs used for the bootstrap loop.

        """
    def __init__(self,
                 n_steps=1000,
                 window_size=0.1,
                 n_bootstraps=3,
                 criteria=criteria.purity_criteria(threshold=0.99),
                 positions=None,
                 conf_index=0,
                 n_jobs=0,
                 curve_file=None,
                 combination_mode='overlapping',
                 min_examples=10,
                 random_state=None):
        self.cut_opts = self.CutOpts(n_steps=n_steps,
                                     window_size=window_size,
                                     n_bootstraps=n_bootstraps,
                                     positions=positions,
                                     combination_mode=combination_mode,
                                     min_examples=min_examples)

        self.criteria = criteria
        self.conf_index = conf_index
        self.n_jobs = n_jobs
        if curve_file is not None:
            self.load_curve(curve_file)
        if not isinstance(random_state, np.random.RandomState):
            random_state = np.random.RandomState(random_state)
        self.random_state = random_state

    def save_curve(self, filename):
        """Function to save a fitted curve. 'numpy.savez' is used to
        store the curve. If the filename doesn't end with '.npz' it is
        added.

        Parameters
        ----------
        filename: str
            Path where the curve is saved.
        """
        cut_curve = self.cut_opts.curve
        np.savez(filename,
                 x=cut_curve.x,
                 y=cut_curve.y,
                 conf_index=self.conf_index)
        return filename

    def load_curve(self, filename):
        """Function to load a fitted curve.

        Parameters
        ----------
        filename: str
            Path from which the curve is loaded.
        """
        if not filename.endswith('.npz'):
            filename += '.npz'
        npzfile = np.load(filename)
        curve = Curve(npzfile['x'], npzfile['y'])
        self.cut_opts.curve = curve
        self.conf_index = int(npzfile['conf_index'])

    def init_curve(self, x, y, conf_index=0):
        """Function to init a fitted curve with x, y.

        Parameters
        ----------
        x : numpy.array
            x positions curves
        y : numpy.array
            y postions of the curve
        conf_index : int, optional
            Index of the confidence_value

        """
        curve = Curve(x, y)
        self.cut_opts.curve = curve
        self.conf_index = int(conf_index)

    class CutOpts(object):
        """Class dealing with all settings of the sliding window.

        Parameters
        ----------
        window_size: float
            Size of the sliding window

        n_steps : integer, optional (default=1000)
            Number of steps for the sliding window

        n_bootstraps : integer (default=3)
            Number of bootstraps. The curve is determined on n_boostraps
            samples and averaged.. The curve is determined on n_boostraps
                samples and averaged.

        criteria : callable, optional (default=purity_criteria(threshold=0.99))
            Funtion criteria(y_true, y_pred, position, sample_weights=None)
            return True/False if the criteria is fulfilled.
            See e.g. purity_criteria

        positions : 1d array-lke, optional (default=None)
            If no positions are provided n_steps equally distributed between
            X_o min/max are used.

        position_type : ['mid', 'mean'], optional (default='mid')
            Type of the postions to the windows. If positions are provided,
            they are used to 'seed' the windows and for further calculations,
            the postions are reevaluated according to the selected type.

        Attributes
        ----------
        window_size: float
            See Parameters window_size

        n_steps : integer
            See Parameters n_steps

        n_bootstraps : integer
            See Parameters n_bootstraps

        criteria : callable
            See Parameters criteria

        positions : 1d array-lke
            See Parameters positions

        position_type : ['mid', 'mean']
            See Parameters position_type
        """
        def __init__(self,
                     n_steps=1000,
                     window_size=0.1,
                     n_bootstraps=10,
                     positions=None,
                     curve_type='mid',
                     combination_mode='overlapping',
                     min_examples=10):
            if positions is not None:
                self.positions = positions
                self.n_steps = len(self.positions)
            else:
                self.n_steps = n_steps
            self.n_bootstraps = n_bootstraps
            self.window_size = window_size
            self.edges = None
            self.positions = positions
            self.curve_type = curve_type
            self.combination_mode = combination_mode
            self.min_examples = min_examples
            self.curve = None

        def init_sliding_windows(self, X_o=None, sample_weight=None):
            """Initilizes the sliding windows.

            Uses the X_o values to determine the edges and the postions
            of all the different windows. If positions were provided in
            the __init__ method, those are used to determine the edges.
            If not the windows are equally distributed between min(X_o)
            and max(X_o). When the edges are set, the positions are
            evaluated according to the position_type set in the
            constructor.

            Parameters
            ----------
            X_o : array-like, shape=(n_samples)
                The input samples. 1d array with the X_o values.

            sample_weight : array-like, shape=(n_samples)
                The input samples. 1d array with the weights.

            Returns
            -------
            edges : array of shape=(n_steps, 2)
                Returns the edges of the sliding windows.
                Lower edges = edges[:, 0]
                Upper edges = edges[:, 1]

            positions : array of shape=(n_steps)
                Returns positions corresponding to the sliding windows.
                See Paremeters positions_type for more infos.
            """
            h_width = self.window_size / 2.
            if self.positions is None:
                assert X_o is not None, 'If not positions are provided, the ' \
                                        'the sliding windows has to be '\
                                        'initiated with data (X_0 != None)'

                min_e = np.min(X_o)
                max_e = np.max(X_o)
                self.positions = np.linspace(min_e + h_width,
                                             max_e - h_width,
                                             self.n_steps)
            self.edges = np.zeros((self.n_steps, 2))
            self.edges[:, 0] = self.positions - h_width
            self.edges[:, 1] = self.positions + h_width

        def generate_cut_curve(self, cut_values):
            """Evaluating all cut values and edges.

            And generates the points of which the cut curve consists.
            Mainly the overlapping of the different windows and the
            averaging of multiple bootsstraps is handeled

            Parameters
            ----------
            cut_values : array-like, shape=(n_steps, n_bootstraps)
                cut_values for each window and bootstraps if
                n_bootstraps > 1

            Returns
            -------
            curve_values : 1-d array
                Values defining the final cut curve
            """
            if self.n_bootstraps > 0:
                cut_values = np.mean(cut_values, axis=1)
            self.curve = CurveSliding(self.edges,
                                      cut_values,
                                      combination_mode=self.combination_mode)
            return self.curve

    def predict(self, X):
        """Predict class for X.
        The predicted class of an input sample is a vote by the trees in
        the forest, weighted by their probability estimates. That is,
        the predicted class is the one with highest mean probability
        estimate across the trees.
        Parameters
        ----------
        X : array-like shape=(n_samples, 2)
            The input samples. With the confidence at index 'conf_index'
            (default=0) and X_o as the other index.
        Returns
        -------
        y_pred : array of shape = [n_samples]
            The predicted classes.
        """
        if self.conf_index == 1:
            new_X = np.zeros_like(X)
            new_X[:, 1] = X[:, 0]
            new_X[:, 0] = X[:, 1]
            X = new_X
        X_o = X[:, 1]
        X_c = X[:, 0]
        thresholds = self.cut_opts.curve(X_o)
        y_pred = np.array(X_c >= thresholds, dtype=int)
        return y_pred

    def fit(self, X, y, sample_weight=None):
        """Fit estimator.
        Parameters
        ----------
        X : array-like shape=(n_samples, 2)
            The input samples. With the confidence at index 'conf_index'
            (default=0) and X_o as the other index.

        y : array-like, shape=(n_samples)
            The target values (class labels in classification,
            possible_classed=[0, 1]).

        sample_weight : array-like, shape=(n_samples) or None
            Sample weights. If None, then samples are equally weighted.

        Returns
        -------
        self : object
            Returns self.
        """
        assert X.shape[1] == 2, 'X must have the shape (n_events, 2)'
        assert len(y) == X.shape[0], 'len(X) and len(y) must be the same'

        if sample_weight is not None:
            assert len(y) == len(sample_weight), 'weights and y need the' \
                'same length'

        if self.conf_index == 1:
            new_X = np.zeros_like(X)
            new_X[:, 1] = X[:, 0]
            new_X[:, 0] = X[:, 1]
            X = new_X

        assert len(np.unique(X[:, 0])) >= 5, 'Less than five different ' \
            ' confidence values!'
        n_events = X.shape[0]
        self.cut_opts.init_sliding_windows(X[:, 1], sample_weight)
        n_bootstraps = self.cut_opts.n_bootstraps
        if n_bootstraps is None or n_bootstraps <= 0:
            cut_values = self.__determine_cut_values_mp__(
                idx=None,
                X_full=X,
                y_full=y,
                sample_weight_full=sample_weight)
        else:
            idx_bootstraps = []
            cut_values = np.zeros((len(self.cut_opts.positions),
                                   n_bootstraps))
            for i in range(n_bootstraps):
                bootstrap = self.random_state.choice(
                    n_events, n_events, replace=True)
                idx_bootstraps.append(np.sort(bootstrap))
            if self.n_jobs > 1:
                n_jobs = min(self.n_jobs, n_bootstraps)
                import time
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=n_jobs) as executor:

                    def future_callback(future):
                        if not future.cancelled():
                            i = future_callback.finished
                            cut_values[:, i] = future.result()
                        else:
                            raise RuntimeError('Subprocess crashed!')
                        future_callback.finished += 1
                        future_callback.running -= 1

                    future_callback.running = 0
                    future_callback.finished = 0

                    for bootstrap in idx_bootstraps:
                        future = executor.submit(
                            self.__determine_cut_values_mp__,
                            idx=bootstrap,
                            X_full=X,
                            y_true_full=y,
                            sample_weight_full=sample_weight)

                        future.add_done_callback(future_callback)
                        future_callback.running += 1
                        while True:
                            if future_callback.running < n_jobs:
                                break
                            else:
                                time.sleep(1)
                    while future_callback.finished < n_bootstraps:
                        time.sleep(1)
            else:
                for i, bootstrap in enumerate(idx_bootstraps):
                    cut_values[:, i] = self.__determine_cut_values_mp__(
                        idx=bootstrap,
                        X_full=X,
                        y_true_full=y,
                        sample_weight_full=sample_weight)
        self.cut_opts.generate_cut_curve(cut_values)
        return self

    def __find_best_cut__(self, i, lower, upper, position,
                          X, y_true, sample_weight, n_points=10):
        X_o = X[:, 1]
        X_c = X[:, 0]
        idx = np.logical_and(X_o >= lower, X_o < upper)
        confidence_i = X_c[idx]
        y_true_i = y_true[idx]
        weights_i = None
        if sample_weight is not None:
            weights_i = sample_weight[idx]

        possible_cuts = np.sort(np.unique(confidence_i))
        if len(possible_cuts) <= self.cut_opts.min_examples:
            return np.nan

        def wrapped_decision_func(cut):
            y_pred_i_j = np.array(confidence_i >= cut, dtype=int)
            return self.criteria(y_true_i,
                                 y_pred_i_j,
                                 position,
                                 sample_weights=weights_i)
        cut_value = self.__find_best_cut_inner__(wrapped_decision_func,
                                                 possible_cuts,
                                                 n_points=n_points)

        return cut_value

    def __find_best_cut_inner__(self, eval_func, conf, n_points=100):
        n_confs = len(conf)
        step_width = int(n_confs / (n_points - 1))
        if len(conf) == 0:
            return np.nan
        if step_width == 0:
            final = True
            selected_cuts = conf
        else:
            final = False
            idx = [(i * step_width) for i in range(n_points)]
            idx[-1] = n_confs - 1
            selected_cuts = conf[idx]
        criteria_values = [eval_func(cut) for cut in selected_cuts]
        idx_min = np.argmin(criteria_values)
        if final:
            return selected_cuts[idx_min]
        else:
            if idx_min == 0:
                conf = conf[:idx[idx_min + 1]]
            elif idx_min == n_points - 1:
                conf = conf[idx[idx_min - 1]:]
            else:
                conf = conf[idx[idx_min - 1]:idx[idx_min + 1]]
            return self.__find_best_cut_inner__(eval_func, conf, n_points)

    def fill_gaps(self, cut_values):
        not_nan_mask = np.array(np.isfinite(cut_values), dtype=int)
        idx_not_nan = np.where(not_nan_mask == 1)[0]
        first_value_idx = idx_not_nan[0]
        last_value_idx = idx_not_nan[-1]
        if first_value_idx != 0:
            cut_values[:first_value_idx] = cut_values[first_value_idx]
            not_nan_mask[:first_value_idx] = 1

        if last_value_idx != 0:
            cut_values[last_value_idx:] = cut_values[last_value_idx]
            not_nan_mask[last_value_idx:] = 1

        diff = np.diff(not_nan_mask)
        falling = np.where(diff == -1)[0]
        rising = np.where(diff == 1)[0]
        for fall, rise in zip(falling, rising):
            idx_first_nan = fall + 1
            idx_last_nan = rise
            value_before = cut_values[idx_first_nan - 1]
            value_after = cut_values[idx_last_nan + 1]
            gap_length = rise - fall
            slope = (value_after - value_before) / (gap_length + 1)
            for i in range(gap_length):
                cut_values[idx_first_nan + i] = value_before + (i + 1) * slope
        return cut_values

    def __determine_cut_values_mp__(self,
                                    idx,
                                    X_full,
                                    y_true_full,
                                    sample_weight_full):
        if idx is None:
            X = X_full
            y_true = y_true_full
            sample_weight = sample_weight_full
        else:
            X = X_full[idx]
            y_true = y_true_full[idx]
            if sample_weight_full is not None:
                sample_weight = sample_weight_full[idx]
            else:
                sample_weight = sample_weight_full

        edges = self.cut_opts.edges
        positions = self.cut_opts.positions
        n_points = 5

        cut_values = np.zeros_like(positions)
        for i, [[lower, upper], position] in enumerate(zip(edges,
                                                           positions)):
            cut_value = self.__find_best_cut__(i, lower, upper, position,
                                               X, y_true, sample_weight,
                                               n_points=n_points)

            cut_values[i] = cut_value
        n_valid_cuts = np.sum(np.isfinite(cut_values))
        if n_valid_cuts == 0:
            raise RuntimeError('No valid cuts found! If manual positions '
                               'being used, they are not in the range of the '
                               'examples!')
        cut_values_filled = self.fill_gaps(cut_values)

        return cut_values_filled

    def __add__(self, other):
        copy = deepcopy(self)
        if isinstance(other, ConfidenceCutter):
            if copy.cut_opts.curve is None:
                copy.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                copy.cut_opts.curve += other.cut_opts.curve
        else:
            try:
                copy.cut_opts.curve += other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return copy

    def __sub__(self, other):
        copy = deepcopy(self)
        if isinstance(other, ConfidenceCutter):
            if copy.cut_opts.curve is None:
                copy.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                copy.cut_opts.curve -= other.cut_opts.curve
        else:
            try:
                copy.cut_opts.curve -= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return copy

    def __mul__(self, other):
        copy = deepcopy(self)
        if isinstance(other, ConfidenceCutter):
            if copy.cut_opts.curve is None:
                copy.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                copy.cut_opts.curve *= other.cut_opts.curve
        else:
            try:
                copy.cut_opts.curve *= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return copy

    def __div__(self, other):
        copy = deepcopy(self)
        if isinstance(other, ConfidenceCutter):
            if copy.cut_opts.curve is None:
                copy.cut_opts.curve /= deepcopy(other.cut_opts.curve)
            else:
                copy.cut_opts.curve /= other.cut_opts.curve
        else:
            try:
                copy.cut_opts.curve /= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return copy

    def __truediv__(self, other):
        copy = deepcopy(self)
        if isinstance(other, ConfidenceCutter):
            if copy.cut_opts.curve is None:
                copy.cut_opts.curve /= deepcopy(other.cut_opts.curve)
            else:
                copy.cut_opts.curve /= other.cut_opts.curve
        else:
            try:
                copy.cut_opts.curve /= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return copy

    def __iadd__(self, other):
        if isinstance(other, ConfidenceCutter):
            if self.cut_opts.curve is None:
                self.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                self.cut_opts.curve += other.cut_opts.curve
        else:
            try:
                self.cut_opts.curve += other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return self

    def __isub__(self, other):
        if isinstance(other, ConfidenceCutter):
            if self.cut_opts.curve is None:
                self.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                self.cut_opts.curve -= other.cut_opts.curve
        else:
            try:
                self.cut_opts.curve -= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return self

    def __imul__(self, other):
        if isinstance(other, ConfidenceCutter):
            if self.cut_opts.curve is None:
                self.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                self.cut_opts.curve *= other.cut_opts.curve
        else:
            try:
                self.cut_opts.curve *= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return self

    def __idiv__(self, other):
        if isinstance(other, ConfidenceCutter):
            if self.cut_opts.curve is None:
                self.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                self.cut_opts.curve /= other.cut_opts.curve
        else:
            try:
                self.cut_opts.curve /= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return self

    def __itruediv__(self, other):
        if isinstance(other, ConfidenceCutter):
            if self.cut_opts.curve is None:
                self.cut_opts.curve = deepcopy(other.cut_opts.curve)
            else:
                self.cut_opts.curve /= other.cut_opts.curve
        else:
            try:
                self.cut_opts.curve /= other
            except TypeError:
                raise TypeError('Valid types [float, int, Curve, '
                                'ConfidenceCutter]')
        return self

    def __call__(self, x):
        return self.cut_opts.curve(x)
