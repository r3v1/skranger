import pickle
import random
import tempfile

import numpy as np
import pytest
from sklearn.base import clone
from sklearn.exceptions import NotFittedError
from sklearn.model_selection import train_test_split
from sklearn.utils.validation import check_is_fitted

from skranger.ensemble import RangerForestRegressor


class TestRangerForestRegressor:
    def test_init(self):
        _ = RangerForestRegressor()

    def test_fit(self, boston_X, boston_y):
        rfr = RangerForestRegressor()
        with pytest.raises(NotFittedError):
            check_is_fitted(rfr)
        rfr.fit(boston_X, boston_y)
        check_is_fitted(rfr)
        assert hasattr(rfr, "ranger_forest_")
        assert hasattr(rfr, "n_features_")

    def test_predict(self, boston_X, boston_y):
        rfr = RangerForestRegressor()
        rfr.fit(boston_X, boston_y)
        pred = rfr.predict(boston_X)
        assert len(pred) == boston_X.shape[0]

    def test_serialize(self, boston_X, boston_y):
        tf = tempfile.TemporaryFile()
        rfr = RangerForestRegressor()
        rfr.fit(boston_X, boston_y)
        pickle.dump(rfr, tf)
        tf.seek(0)
        new_rfr = pickle.load(tf)
        pred = new_rfr.predict(boston_X)
        assert len(pred) == boston_X.shape[0]

    def test_clone(self, boston_X, boston_y):
        rfr = RangerForestRegressor()
        rfr.fit(boston_X, boston_y)
        clone(rfr)

    def test_verbose(self, boston_X, boston_y, verbose, capfd):
        rfc = RangerForestRegressor(verbose=verbose)
        rfc.fit(boston_X, boston_y)
        captured = capfd.readouterr()
        if verbose:
            assert len(captured.out) > 0
        else:
            assert len(captured.out) == 0

    def test_importance(self, boston_X, boston_y, importance, scale_permutation_importance, local_importance):
        rfc = RangerForestRegressor(
            importance=importance,
            scale_permutation_importance=scale_permutation_importance,
            local_importance=local_importance,
        )

        if importance not in ["none", "impurity", "impurity_corrected", "permutation"]:
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)
            return

        rfc.fit(boston_X, boston_y)
        if importance == "none":
            assert rfc.importance_mode_ == 0
        elif importance == "impurity":
            assert rfc.importance_mode_ == 1
        elif importance == "impurity_corrected":
            assert rfc.importance_mode_ == 5
        elif importance == "permutation":
            if local_importance:
                assert rfc.importance_mode_ == 6
            elif scale_permutation_importance:
                assert rfc.importance_mode_ == 2
            else:
                assert rfc.importance_mode_ == 3

    def test_mtry(self, boston_X, boston_y, mtry):
        rfc = RangerForestRegressor(mtry=mtry)

        if callable(mtry) and mtry(5) > 5:
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)
            return
        elif not callable(mtry) and (mtry < 0 or mtry > boston_X.shape[0]):
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)
            return

        rfc.fit(boston_X, boston_y)
        if callable(mtry):
            assert rfc.mtry_ == mtry(boston_X.shape[1])
        else:
            assert rfc.mtry_ == mtry

    def test_inbag(self, boston_X, boston_y):
        inbag = [[1, 2, 3], [2, 3, 4]]
        rfc = RangerForestRegressor(n_estimators=2, inbag=inbag)
        rfc.fit(boston_X, boston_y)

        # inbag list different length from n_estimators
        rfc = RangerForestRegressor(n_estimators=1, inbag=inbag)
        with pytest.raises(ValueError):
            rfc.fit(boston_X, boston_y)

        # can't use inbag with sample weight
        rfc = RangerForestRegressor(inbag=inbag)
        with pytest.raises(ValueError):
            rfc.fit(boston_X, boston_y, sample_weight=[1] * len(boston_y))

        # can't use class sampling and inbag
        rfc = RangerForestRegressor(inbag=inbag, sample_fraction=[1, 1])
        with pytest.raises(ValueError):
            rfc.fit(boston_X, boston_y)

    def test_sample_fraction_replace(self, boston_X, boston_y, replace):
        rfc = RangerForestRegressor(replace=replace)
        rfc.fit(boston_X, boston_y)

        if replace:
            assert rfc.sample_fraction_ == [1.0]
        else:
            assert rfc.sample_fraction_ == [0.632]

    def test_categorical_features(self, boston_X, boston_y, respect_categorical_features):
        # add a categorical feature
        categorical_col = np.atleast_2d(np.array([random.choice([0, 1]) for _ in range(boston_X.shape[0])]))
        boston_X_c = np.hstack((boston_X, categorical_col.transpose()))
        categorical_features = [boston_X.shape[1]]

        rfc = RangerForestRegressor(
            respect_categorical_features=respect_categorical_features, categorical_features=categorical_features
        )

        if respect_categorical_features not in ["partition", "ignore", "order"]:
            with pytest.raises(ValueError):
                rfc.fit(boston_X_c, boston_y)
            return

        rfc.fit(boston_X_c, boston_y)

        if respect_categorical_features in ("ignore", "order"):
            assert rfc.categorical_features_ == []
        else:
            assert rfc.categorical_features_ == [str(c).encode() for c in categorical_features]

    def test_split_rule(self, boston_X, boston_y, split_rule):
        rfc = RangerForestRegressor(split_rule=split_rule)

        if split_rule not in ["variance", "extratrees", "maxstat", "beta"]:
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)
            return

        # beta can only be used with targets between 0 and 1
        if split_rule == "beta":
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)

        boston_01 = [0.5 for _ in boston_y]
        rfc.fit(boston_X, boston_01)

        if split_rule == "variance":
            assert rfc.split_rule_ == 1
        elif split_rule == "extratrees":
            assert rfc.split_rule_ == 5
        elif split_rule == "maxstat":
            assert rfc.split_rule_ == 4
        elif split_rule == "beta":
            assert rfc.split_rule_ == 6

        if split_rule == "extratrees":
            rfc = RangerForestRegressor(
                split_rule=split_rule, respect_categorical_features="partition", save_memory=True
            )
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)
        else:
            rfc = RangerForestRegressor(split_rule=split_rule, num_random_splits=2)
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)

    def test_regularization(self, boston_X, boston_y):
        rfc = RangerForestRegressor()
        rfc.fit(boston_X, boston_y)
        assert rfc.regularization_factor_ == []
        assert not rfc.use_regularization_factor_

        # vector must be between 0 and 1 and length matching feature num
        for r in [[1.1], [-0.1], [1, 1]]:
            rfc = RangerForestRegressor(regularization_factor=r)
            with pytest.raises(ValueError):
                rfc.fit(boston_X, boston_y)

        # vector of ones isn't applied
        rfc = RangerForestRegressor(regularization_factor=[1] * boston_X.shape[1])
        rfc.fit(boston_X, boston_y)
        assert rfc.regularization_factor_ == []
        assert not rfc.use_regularization_factor_

        # regularization vector is used
        reg = [0.5]
        rfc = RangerForestRegressor(regularization_factor=reg, n_jobs=2)
        # warns if n_jobs is not one since parallelization can't be used
        with pytest.warns(Warning):
            rfc.fit(boston_X, boston_y)
        assert rfc.n_jobs_ == 1
        assert rfc.regularization_factor_ == reg
        assert rfc.use_regularization_factor_

    def test_always_split_features(self, boston_X, boston_y):
        rfc = RangerForestRegressor(always_split_features=[0])
        rfc.fit(boston_X, boston_y)
        # feature 0 is in every tree split
        for tree in rfc.ranger_forest_["forest"]["split_var_ids"]:
            assert 0 in tree

    def test_quantile_regression(self, boston_X, boston_y):
        X_train, X_test, y_train, y_test = train_test_split(boston_X, boston_y)
        rfr = RangerForestRegressor(quantiles=False)
        rfr.fit(X_train, y_train)
        assert not hasattr(rfr, "random_node_values_")
        with pytest.raises(ValueError):
            rfr.predict_quantiles(X_test)
        rfr = RangerForestRegressor(quantiles=True)
        rfr.fit(X_train, y_train)
        assert hasattr(rfr, "random_node_values_")
        quantiles_lower = rfr.predict_quantiles(X_test, quantiles=[0.1])
        quantiles_upper = rfr.predict_quantiles(X_test, quantiles=[0.9])
        assert np.less(quantiles_lower, quantiles_upper).all()
        assert quantiles_upper.ndim == 1
        quantiles = rfr.predict_quantiles(X_test, quantiles=[0.1, 0.9])
        assert quantiles.ndim == 2
