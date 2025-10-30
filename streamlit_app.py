 # streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import os
import joblib
import io
import matplotlib.pyplot as plt
from typing import Dict, Any

st.set_page_config(page_title="RainTomorrow Predictor (Streamlit)", layout="wide")
st.title("🌦️ AI Rain Forecast — Streamlit Demo")

# -------------------------
# Utility: find & load model bundle
# -------------------------
MODEL_FILES = [
    "stacking_rain_model_bundle.joblib",
    "stacked_rain_model.joblib",
    "improved_rain_model.joblib",
    "best_rain_model.joblib"
]

@st.cache_resource
def load_model_bundle():
    for p in MODEL_FILES:
        if os.path.exists(p):
            try:
                bundle = joblib.load(p)
                return {"path": p, "bundle": bundle}
            except Exception as e:
                st.warning(f"Found {p} but failed to load: {e}")
    return None

model_info = load_model_bundle()
if model_info:
    st.sidebar.success(f"Loaded model bundle: {model_info['path']}")
else:
    st.sidebar.warning("No model bundle found. Place stacking_rain_model_bundle.joblib or stacked_rain_model.joblib next to this file to use local predictions.")

# -------------------------
# Helpers: preprocessing to match training bundle
# -------------------------
def preprocess_input_df(df: pd.DataFrame, bundle: Dict[str,Any]):
    """
    Apply preprocessing saved inside the model bundle (if present).
    Bundle expected keys (recommended):
      - 'model' : trained sklearn-like estimator
      - 'imputer' : sklearn Imputer
      - 'label_encoders' : dict of LabelEncoder objects
      - 'num_cols' / 'cat_cols' : lists of column names used in training
    If bundle lacks preprocessors, we do minimal cleaning (fillna medians).
    """
    df_proc = df.copy()
    if isinstance(bundle, dict):
        le_map = bundle.get("label_encoders", {})
        imputer = bundle.get("imputer", None)
        num_cols = bundle.get("num_cols", None)
        cat_cols = bundle.get("cat_cols", None)

        # Apply label encoders if present
        if le_map:
            for c, le in le_map.items():
                if c in df_proc.columns:
                    df_proc[c] = df_proc[c].astype(str)
                    try:
                        df_proc[c] = le.transform(df_proc[c])
                    except Exception:
                        # unseen -> map to -1
                        df_proc[c] = df_proc[c].map(lambda v: -1)

        # Numeric imputation
        if imputer is not None:
            # Keep only columns that imputer expects (best-effort)
            cols_to_impute = [c for c in df_proc.columns if c in (num_cols + (cat_cols or []) if num_cols else df_proc.columns.tolist())]
            try:
                df_proc[cols_to_impute] = imputer.transform(df_proc[cols_to_impute])
            except Exception:
                df_proc = df_proc.fillna(df_proc.median(numeric_only=True))
        else:
            df_proc = df_proc.fillna(df_proc.median(numeric_only=True))

        # Reorder / select columns if num_cols defined
        if num_cols:
            expected = [c for c in (num_cols + (cat_cols or [])) if c in df_proc.columns]
            df_proc = df_proc[expected]
    else:
        # bundle is direct model object
        df_proc = df_proc.fillna(df_proc.median(numeric_only=True))
    return df_proc

def predict_from_bundle(df: pd.DataFrame, bundle: Dict[str,Any]):
    """
    Return predictions and probabilities (lists).
    """
    if bundle is None:
        raise ValueError("No model bundle available.")
    if isinstance(bundle, dict):
        model = bundle.get("model")
    else:
        model = bundle

    X = preprocess_input_df(df, bundle) if isinstance(bundle, dict) else df.fillna(df.median(numeric_only=True))
    # Some models require the same column dtypes as trained; user must ensure uploaded CSV matches training features
    preds = model.predict(X)
    probs = None
    try:
        probs = model.predict_proba(X)[:, 1]
    except Exception:
        # Some stacked models may not have predict_proba; fallback to decision_function if available
        try:
            dec = model.decision_function(X)
            probs = 1 / (1 + np.exp(-dec))
        except Exception:
            probs = [None] * len(preds)
    return preds.tolist(), (probs.tolist() if probs is not None else None)

# -------------------------
# Left pane: Single record prediction
# -------------------------
st.header("Single-record prediction")
with st.form("single_form"):
    col1, col2, col3 = st.columns(3)
    location = col1.text_input("Location", value="Sydney")
    min_temp = col1.number_input("MinTemp", value=15.0)
    max_temp = col2.number_input("MaxTemp", value=24.0)
    rainfall = col3.number_input("Rainfall (mm)", value=0.0)
    humidity3pm = col1.number_input("Humidity3pm", value=45.0)
    temp3pm = col2.number_input("Temp3pm", value=22.0)
    rain_today = col3.selectbox("RainToday", options=["No", "Yes"])

    submit_single = st.form_submit_button("Predict single")

if submit_single:
    payload = {
        "Location": location,
        "MinTemp": min_temp,
        "MaxTemp": max_temp,
        "Rainfall": rainfall,
        "Humidity3pm": humidity3pm,
        "Temp3pm": temp3pm,
        "RainToday": "Yes" if rain_today == "Yes" else "No"
    }
    df_payload = pd.DataFrame([payload])
    if model_info:
        try:
            preds, probs = predict_from_bundle(df_payload, model_info["bundle"])
            st.success(f"Prediction (0 = No rain, 1 = Rain): {preds[0]}")
            if probs and probs[0] is not None:
                st.info(f"Probability of rain tomorrow: {probs[0]:.3f}")
            else:
                st.info("Probability not available from model.")
        except Exception as e:
            st.error(f"Prediction failed: {e}")
    else:
        st.warning("No local model bundle found. Upload a model or use the Train option below.")

# -------------------------
# Middle pane: Batch CSV prediction
# -------------------------
st.header("Batch prediction (CSV upload)")
uploaded = st.file_uploader("Upload CSV (each row = a record). Columns should match training features.", type=["csv"])
if uploaded is not None:
    try:
        df_uploaded = pd.read_csv(uploaded)
        st.write("Preview:", df_uploaded.head())
        if st.button("Run batch prediction"):
            if model_info:
                try:
                    preds, probs = predict_from_bundle(df_uploaded, model_info["bundle"])
                    df_out = df_uploaded.copy()
                    df_out["RainTomorrow_pred"] = preds
                    if probs:
                        df_out["RainTomorrow_prob"] = probs
                    st.write("Predictions (first 10 rows):", df_out.head(10))
                    # Allow user to download results
                    towrite = io.BytesIO()
                    df_out.to_csv(towrite, index=False)
                    towrite.seek(0)
                    st.download_button("Download predictions CSV", data=towrite, file_name="rain_predictions.csv")
                except Exception as e:
                    st.error(f"Batch prediction failed: {e}")
            else:
                st.warning("No local model bundle found. Place model next to this file or use Train button to train from your dataset.")
    except Exception as e:
        st.error(f"Failed to read CSV: {e}")

# -------------------------
# Right pane: Train model from weatherAUS.csv (optional)
# -------------------------
st.sidebar.header("Train model (optional)")
st.sidebar.write("If you don't have a saved model bundle, upload the 'weatherAUS.csv' and Train here (takes time & memory).")
train_file = st.sidebar.file_uploader("Upload weatherAUS.csv to train", type=["csv"])
if train_file:
    if st.sidebar.button("Train stacking model now"):
        try:
            with st.spinner("Training stacking ensemble (this can take several minutes)..."):
                df_all = pd.read_csv(train_file, parse_dates=["Date"])
                # Minimal training pipeline (mirrors earlier scripts)
                # 1) drop rows without target
                df_all = df_all.dropna(subset=["RainTomorrow"]).copy()
                df_all["RainTomorrow"] = df_all["RainTomorrow"].map({"No":0,"Yes":1})
                df_all["RainToday"] = df_all["RainToday"].map({"No":0,"Yes":1}).fillna(0)
                # Basic feature engineering
                df_all["day"] = df_all["Date"].dt.day
                df_all["month"] = df_all["Date"].dt.month
                df_all["is_weekend"] = df_all["Date"].dt.weekday.isin([5,6]).astype(int)
                # Select features (pragmatic subset)
                features = [c for c in [
                    "Location","MinTemp","MaxTemp","Rainfall","Evaporation","Sunshine",
                    "WindGustDir","WindGustSpeed","WindDir9am","WindDir3pm","WindSpeed9am","WindSpeed3pm",
                    "Humidity9am","Humidity3pm","Pressure9am","Pressure3pm","Temp9am","Temp3pm",
                    "RainToday","day","month","is_weekend"
                ] if c in df_all.columns]
                df_all = df_all[features + ["Date","RainTomorrow"]]
                # lag features (1-day)
                df_all = df_all.sort_values(["Location","Date"])
                df_all["Rain_lag_1"] = df_all.groupby("Location")["Rainfall"].shift(1).fillna(0)
                # drop rows missing core values
                core = ["MinTemp","MaxTemp"]
                df_all = df_all.dropna(subset=[c for c in core if c in df_all.columns])
                # label encoding for categorical
                from sklearn.preprocessing import LabelEncoder
                le_map = {}
                for c in df_all.select_dtypes(include=["object"]).columns:
                    if c in ("Date",):
                        continue
                    le = LabelEncoder()
                    df_all[c] = df_all[c].astype(str)
                    df_all[c] = le.fit_transform(df_all[c])
                    le_map[c] = le
                # Impute numeric
                from sklearn.impute import SimpleImputer
                imputer = SimpleImputer(strategy="median")
                numeric_cols = df_all.select_dtypes(include=[np.number]).columns.tolist()
                numeric_cols = [c for c in numeric_cols if c != "RainTomorrow"]
                df_all[numeric_cols] = imputer.fit_transform(df_all[numeric_cols])
                # split
                df_all = df_all.sort_values("Date")
                split = int(0.8 * len(df_all))
                train = df_all.iloc[:split]
                test  = df_all.iloc[split:]
                X_train = train[numeric_cols]
                y_train = train["RainTomorrow"]
                X_test  = test[numeric_cols]
                y_test  = test["RainTomorrow"]
                # Build stacking ensemble (XGBoost/LGBM/RF)
                import xgboost as xgb
                import lightgbm as lgb
                from sklearn.ensemble import RandomForestClassifier, StackingClassifier
                from sklearn.linear_model import LogisticRegression
                rf = RandomForestClassifier(n_estimators=200, random_state=42)
                xgb_clf = xgb.XGBClassifier(n_estimators=200, learning_rate=0.08, max_depth=6, use_label_encoder=False, eval_metric="logloss")
                lgb_clf = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, random_state=42)
                estimators = [('xgb', xgb_clf), ('lgb', lgb_clf), ('rf', rf)]
                stack = StackingClassifier(estimators=estimators, final_estimator=LogisticRegression(max_iter=1000), passthrough=True, cv=3, n_jobs=-1)
                stack.fit(X_train, y_train)
                # calibrate probabilities
                from sklearn.calibration import CalibratedClassifierCV
                calibrated = CalibratedClassifierCV(stack, cv=3, method="isotonic")
                calibrated.fit(X_train, y_train)
                # evaluate quickly
                preds = calibrated.predict(X_test)
                probs = calibrated.predict_proba(X_test)[:,1]
                from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
                acc = accuracy_score(y_test, preds)
                f1 = f1_score(y_test, preds)
                auc = roc_auc_score(y_test, probs)
                st.success(f"Training complete. Test Accuracy: {acc:.4f}, F1: {f1:.4f}, AUC: {auc:.4f}")
                # Save bundle
                bundle = {
                    "model": calibrated,
                    "imputer": imputer,
                    "label_encoders": le_map,
                    "num_cols": numeric_cols,
                    "cat_cols": [c for c in le_map.keys()]
                }
                joblib.dump(bundle, "stacking_rain_model_bundle.joblib")
                st.success("Saved model bundle -> stacking_rain_model_bundle.joblib (in app folder). Refresh app to load it.")
        except Exception as e:
            st.error(f"Training failed: {e}")

# -------------------------
# SHAP explainability (if model present)
# -------------------------
st.header("Explainability (SHAP)")
if model_info:
    try:
        bundle = model_info["bundle"]
        model = bundle["model"] if isinstance(bundle, dict) else bundle
        if st.button("Compute SHAP summary (sample)"):
            st.info("Computing SHAP values on a small sample (may take some time)...")
            # prepare small X_test sample from a sample CSV if available, else request user to upload test CSV
            sample_file = st.file_uploader("Optional: upload a sample small CSV to compute SHAP (else uses recent training file if available)", type=["csv"], key="shap_sample")
            if sample_file:
                df_sample = pd.read_csv(sample_file)
                X_sample = preprocess_input_df(df_sample, bundle) if isinstance(bundle, dict) else df_sample.fillna(df_sample.median(numeric_only=True))
            else:
                # quick try: take small slice from last uploaded CSV or abort
                st.warning("No sample uploaded. Please upload a small CSV (<=1000 rows) with same features as training to compute SHAP.")
                X_sample = None

            if X_sample is not None:
                import shap
                try:
                    # choose an appropriate explainer if model supports tree-based
                    if hasattr(model, "predict_proba") and hasattr(model, "estimators_"):
                        # attempt to use a tree explainer on one of the base estimators (if stacked)
                        base_est = None
                        if hasattr(model, "estimators_"):
                            # try to pick an XGBoost / LGBM inside estimators_
                            for name, est in model.estimators_:
                                if hasattr(est, "feature_importances_") or "xgb" in str(type(est)).lower() or "lgb" in str(type(est)).lower():
                                    base_est = est
                                    break
                        explainer = shap.Explainer(base_est if base_est is not None else model, X_sample)
                        shap_values = explainer(X_sample)
                        st.set_option('deprecation.showPyplotGlobalUse', False)
                        fig = shap.summary_plot(shap_values, X_sample, show=False)
                        st.pyplot(bbox_inches='tight')
                    else:
                        st.warning("Model not compatible for tree SHAP. Try a lighter explainer or upload a smaller sample.")
                except Exception as e:
                    st.error(f"SHAP failed: {e}")
    except Exception as e:
        st.error(f"Explainability error: {e}")
else:
    st.info("No loaded model bundle — cannot compute SHAP. Train or upload model bundle.")

# Footer
st.markdown("---")
st.caption("Built for GTU project / internship demo. Ensure your uploaded CSV columns match the training features for reliable predictions.")
