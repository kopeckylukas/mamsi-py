# -*- coding: utf-8 -*-
#
# Author:   Lukas Kopecky <l.kopecky22@imperial.ac.uk>
#           Timothy MD Ebbels
#
# License: 3-clause BSD

import copy as deepcopy
import pandas as pd
import numpy as np
import statistics
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score, accuracy_score, confusion_matrix,
                             ConfusionMatrixDisplay)
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score
from mbpls.mbpls import MBPLS
from sklearn.utils.validation import check_array, check_is_fitted
import matplotlib.pyplot as plt
plt.rc('font', family='Verdana')


class MamsiPls(MBPLS):
    def __init__(self, n_components=2, full_svd=False, method='NIPALS', standardize=True, max_tol=1e-14,
                 nipals_convergence_norm=2, calc_all=True, sparse_data=False, copy=True):
        """
        A wrapper of Multi-block PLS regression for predictive modelling using latent variables
        based on MB-PLS package: Baum et al., (2019). Multiblock PLS: Block dependent prediction modeling for Python.
        This wrapper has some extra methods convenient in Chemometrics and Metabolomics research.

        :param n_components: int Number
            (:math:`k`) of Latent Variables (LV)
        :param full_svd:bool (default True)
            Using full singular value decomposition when performing SVD method.
            Set to 'False' when using very large quadratic matrices :math:`X`.
        :param method: string (default 'NIPALS')
            The method being used to derive the model attributes, possible are 'UNIPALS', 'NIPALS', 'SIMPLS' and
            'KERNEL'
        :param standardize: bool (default True)
            Standardising the data (Unit-variance scaling)
        :param max_tol: non-negative float (default 1e-14)
            Maximum tolerance allowed when using the iterative NIPALS algorithm

        :param nipals_convergence_norm: {non-zero int, inf, -inf, 'fro', 'nuc'} (default 2)
            Order of the norm that is used to calculate the difference of the super-score vectors between subsequent
            iterations of the NIPALS algorithm. Following orders are available:

            =====  ============================  ==========================
            ord    norm for matrices             norm for vectors
            =====  ============================  ==========================
            None   Frobenius norm                2-norm
            'fro'  Frobenius norm                --
            'nuc'  nuclear norm                  --
            inf    max(sum(abs(x), axis=1))      max(abs(x))
            -inf   min(sum(abs(x), axis=1))      min(abs(x))
            0      --                            sum(x != 0)
            1      max(sum(abs(x), axis=0))      as below
            -1     min(sum(abs(x), axis=0))      as below
            2      2-norm (largest sing. value)  as below
            -2     smallest singular value       as below
            other  --                            sum(abs(x)**ord)**(1./ord)
            =====  ============================  ==========================
        :param calc_all: bool (default True)
            Calculate all internal attributes for the used method. Some methods do not need to calculate all attributes,
            i.e. scores, weights etc., to obtain the regression coefficients used for prediction. Setting this parameter
            to false will omit these calculations for efficiency and speed.
        :param sparse_data: bool (default False)
            NIPALS is the only algorithm that can handle sparse data using the method of H. Martens and Martens (2001)
            (p. 381). If this parameter is set to 'True', the method will be forced to NIPALS and sparse data is
            allowed.
            Without setting this parameter to 'True', sparse data will not be accepted.
        :param copy: bool (default True)
            Whether the deflation should be done on a copy. Not using a copy might alter the input data and have
            unforeseeable consequences.
        """
        super().__init__(n_components, full_svd, method, standardize, max_tol, nipals_convergence_norm,
                         calc_all, sparse_data, copy)

    def estimate_lv(self, x, y, n_components=10, no_fold=5, y_continuous=False, metric='auc',
                    plateau_threshold=0.01, increase_threshold=0.05, get_scores=False):
        """
        Method to estimate the number of latent variables (components) for MAMSI MB-PLS model.
        :param x: array, list[array]
            of all blocks of predictors x1, x2, ..., xn. Rows are observations, columns are features/variables.
        :param y: array
            1-dim or 2-dim array of reference values, either continuous or categorical variable.
        :param n_components: int (default 10)
            Number of components / latent variables.
        :param no_fold: int (default 5)
            Number of folds for k-fold cross-validation.
        :param y_continuous: boolean (default False)
            Is outcome a continuous variable.
        :param metric: string (default 'AUC')
            metric: Metric to use to estimate the number of LVs; available:['AUC', q2, 'precision', 'recall', 'f1'].
        :param plateau_threshold: non-negative float (default 0.01)
            Maximum increase for a sequence of LVs to be considered plateau.
        :param increase_threshold: non-negative float (default 0.05)
            Minimum increase to be considered a bend.
        :param get_scores: boolean (default False)
            Return measured scores as a dataframe; default False.
        :return: Measured scores as Pandas dataframe.
        """

        # Validation of data inputs
        data = x.copy()
        # Check if the data is a list of a dataframe
        if isinstance(data, list) and not isinstance(data[0], list):
            pass
        else:
            data = [data]

        _y = check_array(y, ensure_2d=False)
        response_y = _y.copy()

        # Validation in parameter inputs
        if y_continuous:
            metric = 'q2'
            allowed_metrics = ['q2']
            if metric not in allowed_metrics:
                raise ValueError(f"Invalid metric continuous outcome. Allowed values are: {', '.join(allowed_metrics)}")
        else:
            allowed_metrics = ['auc', 'precision', 'recall', 'f1', 'accuracy']
            if metric not in allowed_metrics:
                raise ValueError(f"Invalid metric for categorical outcome. Allowed values are: "
                                 f"{', '.join(allowed_metrics)}")

        # Scores placeholders
        r2 = []
        q2 = []
        r2_auc = []
        r2_precision = []
        r2_recall = []
        r2_f1 = []
        r2_accuracy = []
        q2_auc = []
        q2_precision = []
        q2_recall = []
        q2_f1 = []
        q2_accuracy = []

        # define splits
        kf = KFold(n_splits=no_fold)
        kf.get_n_splits(response_y)

        # Estimation of scores for different number of latent variables / components.
        for i in range(1, n_components + 1):

            # Set LV scores placeholder lists
            lv_r2 = []
            lv_q2 = []
            lv_r2_precision = []
            lv_r2_recall = []
            lv_r2_auc = []
            lv_r2_f1 = []
            lv_r2_accuracy = []
            lv_q2_precision = []
            lv_q2_recall = []
            lv_q2_auc = []
            lv_q2_f1 = []
            lv_q2_accuracy = []

            for j, (train_indices, test_indices) in enumerate(kf.split(response_y)):

                # Unwrap data perform test-train split
                train_data = [None] * len(data)
                test_data = [None] * len(data)
                train_test_data = [None] * len(data)
                for k in range(len(data)):
                    train_data[k] = data[k].iloc[train_indices]  # filter training data by index and save in a new list
                    test_data[k] = data[k].iloc[test_indices]  # filter testing data by index and save in a new list
                    train_test_data[k] = data[k].iloc[train_indices]

                # for each n_components fit new model
                self.n_components = i
                self.fit_transform(train_data, response_y[train_indices])

                # Predict outcome based on training folds
                y_predicted_train = self.predict(train_test_data)
                # Calculate predictive performance of training folds
                if y_continuous:
                    lv_r2.append(r2_score(response_y[train_indices], y_predicted_train))
                else:
                    lv_r2_auc.append(roc_auc_score(response_y[train_indices], y_predicted_train))
                    lv_r2_precision.append(precision_score(response_y[train_indices],
                                                           np.where(y_predicted_train > 0.5, 1, 0)))
                    lv_r2_recall.append(
                        recall_score(response_y[train_indices], np.where(y_predicted_train > 0.5, 1, 0)))
                    lv_r2_f1.append(f1_score(response_y[train_indices], np.where(y_predicted_train > 0.5, 1, 0)))
                    lv_r2_accuracy.append(
                        accuracy_score(response_y[train_indices], np.where(y_predicted_train > 0.5, 1, 0)))

                # Predict outcome based on testing folds
                y_predicted_test = self.predict(test_data)
                # Calculate predictive performance of testing folds
                if y_continuous:
                    lv_q2.append(r2_score(response_y[test_indices], y_predicted_test))
                else:
                    lv_q2_auc.append(roc_auc_score(response_y[test_indices], y_predicted_test))
                    lv_q2_precision.append(precision_score(response_y[test_indices],
                                                           np.where(y_predicted_test > 0.5, 1, 0)))
                    lv_q2_recall.append(recall_score(response_y[test_indices], np.where(y_predicted_test > 0.5, 1, 0)))
                    lv_q2_f1.append(f1_score(response_y[test_indices], np.where(y_predicted_test > 0.5, 1, 0)))
                    lv_q2_accuracy.append(
                        accuracy_score(response_y[test_indices], np.where(y_predicted_test > 0.5, 1, 0)))

            # Calculate mean scores of predictive performance for training and testing folds across for each LV
            if y_continuous:
                r2.append(statistics.mean(lv_r2))
                q2.append(statistics.mean(lv_q2))
            else:
                r2_auc.append(statistics.mean(lv_r2_auc))
                q2_auc.append(statistics.mean(lv_q2_auc))
                r2_precision.append(statistics.mean(lv_r2_precision))
                r2_recall.append(statistics.mean(lv_r2_recall))
                r2_f1.append(statistics.mean(lv_r2_f1))
                r2_accuracy.append(statistics.mean(lv_r2_accuracy))
                q2_precision.append(statistics.mean(lv_q2_precision))
                q2_recall.append(statistics.mean(lv_q2_recall))
                q2_f1.append(statistics.mean(lv_q2_f1))
                q2_accuracy.append(statistics.mean(lv_q2_accuracy))

        if y_continuous:
            perf_scores = pd.DataFrame([range(1, n_components + 1), r2, q2],
                                       index=['Number of Components', 'r2', 'q2']).T
        else:
            perf_scores = pd.DataFrame([range(1, n_components + 1), r2_auc, r2_precision, r2_recall, r2_f1,
                                        r2_accuracy, q2_auc, q2_precision, q2_recall, q2_f1, q2_accuracy],
                                       index=['Number of Components', 'Training AUC', 'Training Precision',
                                              'Training Recall', 'Training F1 Score', 'Training Accuracy',
                                              'Testing AUC', 'Testing Precision', 'Testing Recall',
                                              'Testing F1 Score', 'Testing Accuracy']).T

        # Select desired metric
        if metric == 'q2':
            data = q2
        if metric == 'auc':
            data = q2_auc
        if metric == 'precision':
            data = q2_precision
        if metric == 'recall':
            data = q2_recall
        if metric == 'f1':
            data = q2_f1
        if metric == 'accuracy':
            data = q2_accuracy

        # Estimate number of LVs
        bend = np.min(np.where(np.diff(data) / data[0] < increase_threshold)[0]) + 1
        plateau_range_start, plateau_range_end = self._find_plateau(data, range_threshold=plateau_threshold)

        # Percentage for printed statements below
        increase = increase_threshold * 100

        # Plot the results
        perf_scores.plot.line(x='Number of Components', marker='.', figsize=(8, 6), grid=False)
        plt.xlim(0, n_components + 1)
        plt.xticks(np.arange(1, n_components + 1, 1.0))
        try:
            plt.axvline(plateau_range_start, linestyle='--', color='r', label='Plateau edge')
            plt.axvline(bend, linestyle='dotted', color='b', label='Bend')
            print(metric + " reaches bent (increase of less than {0}".format(increase) +
                  " % of previous value or decrease) at component {0}".format(bend))
            print(metric + " reaches plateau at component {0}".format(plateau_range_start))
            self.n_components = plateau_range_start
            self.fit(x, y)
            print("Model re-fitted with n_components =", self.n_components)
        except TypeError:
            print(metric + " reaches bend (increase of less than {0}".format(increase) +
                  " % of previous value or decrease) at component {0}".format(bend))
            plt.axvline(bend, linestyle='--', color='b', label='Bend')
            print('No plateau detected, consider exploring more latent variables.')
            self.n_components = bend
            self.fit(x, y)
            print("Model re-fitted with n_components =", self.n_components)
        plt.ylabel('Score')
        plt.xlabel('Number of Latent Variables')
        plt.title('Latent Variable Estimation')
        plt.legend()

        if get_scores:
            return perf_scores

    def evaluate_class_model(self, x, y):
        """
        Evaluate MB-PLS model using a **testing** dataset.
        :param x: array, list[array]
            of all blocks of predictors x1, x2, ..., xn. Rows are observations, columns are features/variables.
        :param y: array
            1-dim or 2-dim array of reference values, either continuous or categorical variable.
        :return: predicted y variable based on training set predictors
        """

        # Check if PLS model is fitted
        check_is_fitted(self, 'beta_')

        # Validate inputs
        _x = x.copy()
        if isinstance(_x, list) and not isinstance(_x[0], list):
            pass
        else:
            _x = [x]
        _y = y.copy()
        _y = check_array(_y, ensure_2d=False)

        # Predict test data
        y_predicted = self.predict(_x)

        # Evaluation metrics
        cm2 = confusion_matrix(y, np.where(y_predicted > 0.5, 1, 0))
        disp2 = ConfusionMatrixDisplay(confusion_matrix=cm2)
        disp2.plot()
        print('Scores for model with n_components =', self.n_components)
        print('\nAccuracy', round(accuracy_score(_y, np.where(y_predicted > 0.5, 1, 0)), 3))
        print('Precision', round(precision_score(_y, np.where(y_predicted > 0.5, 1, 0)), 3))
        print('Recall', round(recall_score(_y, np.where(y_predicted > 0.5, 1, 0)), 3))
        tn, fp, fn, tp = confusion_matrix(_y, np.where(y_predicted > 0.5, 1, 0)).ravel()
        print('Specificity', round(tn/(tn+fp), 3))
        print('F1 Score', round(f1_score(_y, np.where(y_predicted > 0.5, 1, 0)), 3))
        print('AUC', round(roc_auc_score(_y, y_predicted), 3))
        return y_predicted

    def mb_vip(self, plot=False):
        """
        Multi-block Variable importance in projection (MB-VIP) for multiblock PLS model.
        Adaptation of C. Wieder et al., (2024). PathIntegrate, doi: 10.1371/journal.pcbi.1011814.
        :param plot: boolean (default False)
            Plot MB-VIP scores.
        :return: MB-VIP scores
        """
        # Check is model is fitted
        check_is_fitted(self, 'beta_')

        # stack the weights from all blocks
        weights = np.vstack(self.W_)
        # calculate product of sum of squares of super scores and y loadings
        sum_squares = np.sum(self.Ts_ ** 2, axis=0) * np.sum(self.V_ ** 2, axis=0)
        # p = number of variables - stack the loadings from all blocks
        p = np.vstack(self.P_).shape[0]
        # VIP is a weighted sum of squares of PLS weights
        vip_scores = np.sqrt(p * np.sum(sum_squares * (weights ** 2), axis=1) / np.sum(sum_squares))

        # Plot VIP scores
        if plot:
            plt.plot(vip_scores, color='limegreen', linewidth=0.8)
            plt.title('Multi-block variable importance in projection')
            plt.ylabel('MB-VIP score')
            plt.xlabel('Feature index')

        # Return all MB-VIP scores
        return vip_scores

    def mb_vip_permtest(self, x, y, n_permutations=1000, return_scores=False):
        """
        Calculate empirical p-values for each feature by permuting the Y outcome variable "n_permutations" times and
        refitting the model; the p-values for each feature were then calculated by counting the number of trials with
        MB-VIP greater than or equal to the observed test statistic, and dividing this by "n_permutations".

        N.B. This method uses OpenMP to parallelise the code, relying on multi-threading exclusively. By default,
        the implementations using OpenMP will use as many threads as possible, i.e. as many threads as logical cores.
        This is available by default on systems with macOS and MS Windows.
        Running this method on a High Performance Computing (HPC), including Imperial College London HPC, requires
        additional Joblib parallelisation. Such parallelised permtest function can be found ./Extras directory
        as parallel_mb_vip_permtest.py. If you are Imperial colleague, do not hesitate to contact me for support on how
        to set up PBS file.

        :param x: array, list[array]
            of all blocks of predictors x1, x2, ..., xn. Rows are observations, columns are features/variables.
        :param y: array
            1-dim or 2-dim array of reference values, either continuous or categorical variable.
        :param n_permutations: int (default 1000)
            Number of permutation tests.
        :param return_scores: boolean (default False)
            Should method return
        :return: Returns array of p-values for each feature. If 'n_permutations' == True, then a matrix of MB-VIP scores
            for each permuted null model is returned as well.
        """

        # Check is model is fitted
        check_is_fitted(self, 'beta_')

        # Validation of data inputs
        _x = deepcopy.deepcopy(x)  # deepcopy to prevent data leakage
        if isinstance(_x, list) and not isinstance(_x[0], list):
            pass
        else:
            _x = [_x]
        _y = y.copy()
        _y = check_array(_y, ensure_2d=False)

        # MB-VIP of observed model
        _vip = self.mb_vip()
        vip_obs = _vip[:, np.newaxis]

        # Fit Null models
        _vip_null = []
        for i in range(n_permutations):
            # Permute outcome
            y_perm = np.random.permutation(_y)
            # Fit permuted model and calculate MB-VIP scores
            self.fit(x, y_perm)
            _vip_null.append(self.mb_vip())
        vip_null = np.stack(_vip_null, axis=1)

        # Calculate empirical p-values
        vip_greater = np.sum(vip_null >= vip_obs, axis=1)
        p_vals = vip_greater/n_permutations

        # Return p-vales and MB-PLS scores for null models
        if return_scores:
            return p_vals, vip_null
        else:
            return p_vals

    @staticmethod
    def _find_plateau(scores, range_threshold=0.01, consecutive_elements=3):
        """
        Function to assist find a plateau in sequence of LVs.
        :param scores: List of scores.
        :param range_threshold: Maximum increase for a sequence of LVs to be considered plateau; default 0.01.
        :param consecutive_elements: Number of elements that need to be in a plateau; default 3.
        :return: Beginning and end of the plateau.
        """
        n = len(scores)
        for i in range(1, n - consecutive_elements + 1):
            plateau = True
            for j in range(consecutive_elements - 1):
                diff = abs(scores[i + j] - scores[i + j - 1])
                if diff > range_threshold:
                    plateau = False
                    break
            if plateau:
                return i, i + consecutive_elements - 1

        # If no plateau is found, return a tuple of None
        return None, None
