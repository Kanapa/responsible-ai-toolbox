# Copyright (c) Microsoft Corporation
# Licensed under the MIT License.

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from tempfile import TemporaryDirectory
from common_utils import (create_boston_data,
                          create_cancer_data,
                          create_iris_data,
                          create_binary_classification_dataset,
                          create_models_classification,
                          create_models_regression)

from responsibleai import ModelAnalysis, ModelTask
from responsibleai._internal.constants import ManagerNames

from causal_manager_validator import validate_causal
from counterfactual_manager_validator import validate_counterfactual
from error_analysis_validator import (
    setup_error_analysis, validate_error_analysis)
from explainer_manager_validator import setup_explainer, validate_explainer


LABELS = "labels"
DESIRED_CLASS = 'desired_class'
DESIRED_RANGE = 'desired_range'


class TestModelAnalysis(object):

    @pytest.mark.parametrize('manager_type', [ManagerNames.COUNTERFACTUAL,
                                              ManagerNames.ERROR_ANALYSIS,
                                              ManagerNames.EXPLAINER])
    def test_model_analysis_iris(self, manager_type):
        x_train, x_test, y_train, y_test, feature_names, classes = \
            create_iris_data()
        x_train = pd.DataFrame(x_train, columns=feature_names)
        x_test = pd.DataFrame(x_test, columns=feature_names)
        models = create_models_classification(x_train, y_train)
        x_train[LABELS] = y_train
        x_test[LABELS] = y_test
        manager_args = {DESIRED_CLASS: 0}

        for model in models:
            run_model_analysis(model, x_train, x_test, LABELS, [],
                               manager_type, manager_args, classes)

    @pytest.mark.parametrize('manager_type', [ManagerNames.ERROR_ANALYSIS,
                                              ManagerNames.COUNTERFACTUAL,
                                              ManagerNames.EXPLAINER])
    def test_model_analysis_cancer(self, manager_type):
        x_train, x_test, y_train, y_test, feature_names, classes = \
            create_cancer_data()
        x_train = pd.DataFrame(x_train, columns=feature_names)
        x_test = pd.DataFrame(x_test, columns=feature_names)
        models = create_models_classification(x_train, y_train)
        x_train[LABELS] = y_train
        x_test[LABELS] = y_test
        manager_args = {DESIRED_CLASS: 'opposite'}

        for model in models:
            run_model_analysis(model, x_train, x_test, LABELS, [],
                               manager_type, manager_args, classes)

    @pytest.mark.parametrize('manager_type', [ManagerNames.CAUSAL,
                                              ManagerNames.ERROR_ANALYSIS,
                                              ManagerNames.EXPLAINER])
    def test_model_analysis_binary(self, manager_type):
        x_train, y_train, x_test, y_test, classes = \
            create_binary_classification_dataset()
        x_train = pd.DataFrame(x_train)
        x_test = pd.DataFrame(x_test)
        models = create_models_classification(x_train, y_train)
        x_train[LABELS] = y_train
        x_test[LABELS] = y_test
        manager_args = None

        for model in models:
            run_model_analysis(model, x_train, x_test, LABELS, [],
                               manager_type, manager_args,
                               classes=classes)

    @pytest.mark.parametrize('manager_type', [ManagerNames.CAUSAL,
                                              ManagerNames.COUNTERFACTUAL,
                                              ManagerNames.EXPLAINER])
    def test_modelanalysis_boston(self, manager_type):
        x_train, x_test, y_train, y_test, feature_names = \
            create_boston_data()
        x_train = pd.DataFrame(x_train, columns=feature_names)
        x_test = pd.DataFrame(x_test, columns=feature_names)
        models = create_models_regression(x_train, y_train)
        x_train[LABELS] = y_train
        x_test[LABELS] = y_test
        manager_args = {DESIRED_RANGE: [10, 20]}

        for model in models:
            run_model_analysis(model, x_train, x_test, LABELS, ['RM'],
                               manager_type, manager_args)


def run_model_analysis(model, train_data, test_data, target_column,
                       categorical_features, manager_type,
                       manager_args=None, classes=None):
    if classes is not None:
        task_type = ModelTask.CLASSIFICATION
    else:
        task_type = ModelTask.REGRESSION

    if manager_type == ManagerNames.COUNTERFACTUAL:
        test_data = test_data[0:1]

    model_analysis = ModelAnalysis(model, train_data, test_data,
                                   target_column,
                                   categorical_features=categorical_features,
                                   task_type=task_type)

    if manager_type == ManagerNames.EXPLAINER:
        setup_explainer(model_analysis)
    elif manager_type == ManagerNames.ERROR_ANALYSIS:
        setup_error_analysis(model_analysis)

    validate_model_analysis(model_analysis, train_data, test_data,
                            target_column, task_type)

    if manager_type == ManagerNames.CAUSAL:
        validate_causal(model_analysis, train_data, target_column)
    elif manager_type == ManagerNames.COUNTERFACTUAL:
        desired_range = None
        desired_class = None
        if manager_args is not None:
            if DESIRED_CLASS in manager_args:
                desired_class = manager_args[DESIRED_CLASS]
            if DESIRED_RANGE in manager_args:
                desired_range = manager_args[DESIRED_RANGE]
        validate_counterfactual(model_analysis, train_data, target_column,
                                desired_class, desired_range)
    elif manager_type == ManagerNames.ERROR_ANALYSIS:
        validate_error_analysis(model_analysis)
    elif manager_type == ManagerNames.EXPLAINER:
        validate_explainer(model_analysis, train_data, test_data, classes)

    with TemporaryDirectory() as tempdir:
        path = Path(tempdir) / 'rai_test_path'
        # save the model_analysis
        model_analysis.save(path)
        # load the model_analysis
        model_analysis = ModelAnalysis.load(path)

        if manager_type == ManagerNames.EXPLAINER:
            setup_explainer(model_analysis)

        validate_model_analysis(model_analysis, train_data, test_data,
                                target_column, task_type)

        if manager_type == ManagerNames.ERROR_ANALYSIS:
            validate_error_analysis(model_analysis)
        elif manager_type == ManagerNames.EXPLAINER:
            validate_explainer(model_analysis, train_data, test_data, classes)


def validate_model_analysis(
    model_analysis,
    train_data,
    test_data,
    target_column,
    task_type
):
    pd.testing.assert_frame_equal(model_analysis.train, train_data)
    pd.testing.assert_frame_equal(model_analysis.test, test_data)
    assert model_analysis.target_column == target_column
    assert model_analysis.task_type == task_type
    np.testing.assert_array_equal(model_analysis._classes,
                                  train_data[target_column].unique())