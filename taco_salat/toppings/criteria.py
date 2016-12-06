#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np

def purity_criteria(threshold=0.99):
    """Returns decisison function which returns if the desired purity
    is fulfilled.
    Parameters
    ----------
    threshold : float or callable
        If float, independent from the positon of the window a constant
        criteria, which has to be fulfilled for each windowd, is used.
        If callable the function has to take the position and return a
        criteria not greater than 1.
    Returns
    -------
    decisison function : callable
        Returns a func(y_true, y_pred, position, sample_weights=None)
        returning 'fulfilled' which indicated if the desired purity is
        fulfilled.
    """
    if isinstance(threshold, float):
        if threshold > 1.:
            raise ValueError('Constant threshold must be <= 1')
        threshold_func = lambda x: threshold
    elif callable(threshold):
        threshold_func = threshold
    else:
        raise TypeError('\'threshold\' must be either float or callable')

    def decision_function(y_true, y_pred, position, sample_weights=None):
        """Returns decisison function which returns if the desired purity
        is fulfilled.
        Parameters
        ----------
        y_true : 1d array-like
            Ground truth (correct) target values. Only binary
            classification is supported.

        y_pred : 1d array-like
            Estimated targets.

        position : float
            Value indicating the postion of the cut window.

        Returns
        -------
        fulfilled : boolean
            Return if the criteria is fulfilled.
        """
        float_criteria = threshold_func(position)
        if not isinstance(float_criteria, float):
            raise TypeError('Callable threshold must return float <= 1.')
        if float_criteria > 1.:
            raise ValueError('Callable threshold returned value > 1')
        y_true_bool = np.array(y_true, dtype=bool)
        y_pred_bool = np.array(y_pred, dtype=bool)
        if sample_weights is None:
            tp = np.sum(y_true_bool[y_pred_bool])
            fp = np.sum(~y_true_bool[y_pred_bool])
        else:
            idx_tp = np.logical_and(y_true_bool, y_pred_bool)
            idx_fp = np.logical_and(~y_true_bool, y_pred_bool)
            tp = np.sum(sample_weights[idx_tp])
            fp = np.sum(sample_weights[idx_fp])
        if tp + fp == 0:
            purity = 0.
        else:
            purity = tp / (tp + fp)
        return np.absolute(purity - float_criteria)

    return decision_function
