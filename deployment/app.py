"""
FastAPI application for Bank Marketing Term Deposit Prediction Service

This module provides a REST API for making predictions using trained ML models.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
import logging
import os

# Prometheus metrics
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Bank Marketing Prediction API",
    description="ML-powered API for predicting term deposit subscription",
    version="1.0.0"
)

# Prometheus metrics
PREDICTIONS_COUNTER = Counter(
    'predictions_total', 
    'Total number of predictions', 
    ['model_name', 'prediction']
)
PREDICTION_LATENCY = Histogram(
    'prediction_latency_seconds', 
    'Prediction latency in seconds',
    ['model_name']
)
ERRORS_COUNTER = Counter(
    'prediction_errors_total', 
    'Total number of prediction errors',
    ['error_type']
)

# Global model storage
models = {}
preprocessor = None
label_encoder = None
feature_names = None


class PredictionInput(BaseModel):
    """Input schema for prediction requests"""
    age: int = Field(..., ge=18, le=100, description="Customer age")
    job: str = Field(..., description="Type of job")
    marital: str = Field(..., description="Marital status")
    education: str = Field(..., description="Education level")
    default: str = Field(..., description="Has credit in default?")
    balance: float = Field(..., description="Average yearly balance in euros")
    housing: str = Field(..., description="Has housing loan?")
    loan: str = Field(..., description="Has personal loan?")
    contact: str = Field(..., description="Contact communication type")
    day: int = Field(..., ge=1, le=31, description="Last contact day of month")
    month: str = Field(..., description="Last contact month of year")
    duration: int = Field(..., ge=0, description="Last contact duration in seconds")
    campaign: int = Field(..., ge=1, description="Number of contacts during this campaign")
    pdays: int = Field(..., description="Days since last contact from previous campaign")
    previous: int = Field(..., ge=0, description="Number of contacts before this campaign")
    poutcome: str = Field(..., description="Outcome of previous marketing campaign")
    
    # Optional fields (for enhanced dataset)
    day_of_week: Optional[str] = Field(None, description="Last contact day of the week")
    emp_var_rate: Optional[float] = Field(None, description="Employment variation rate")
    cons_price_idx: Optional[float] = Field(None, description="Consumer price index")
    cons_conf_idx: Optional[float] = Field(None, description="Consumer confidence index")
    euribor3m: Optional[float] = Field(None, description="Euribor 3 month rate")
    nr_employed: Optional[float] = Field(None, description="Number of employees")
    
    class Config:
        schema_extra = {
            "example": {
                "age": 45,
                "job": "management",
                "marital": "married",
                "education": "tertiary",
                "default": "no",
                "balance": 2500.0,
                "housing": "yes",
                "loan": "no",
                "contact": "cellular",
                "day": 15,
                "month": "may",
                "duration": 300,
                "campaign": 2,
                "pdays": 999,
                "previous": 0,
                "poutcome": "unknown",
                "day_of_week": "mon",
                "emp_var_rate": 1.1,
                "cons_price_idx": 93.994,
                "cons_conf_idx": -36.4,
                "euribor3m": 4.857,
                "nr_employed": 5191.0
            }
        }


class PredictionOutput(BaseModel):
    """Output schema for prediction responses"""
    prediction: str = Field(..., description="Predicted class (yes/no)")
    probability: float = Field(..., description="Probability of subscription")
    model: str = Field(..., description="Model used for prediction")
    timestamp: str = Field(..., description="Prediction timestamp")
    version: str = Field(..., description="API version")


class BatchPredictionInput(BaseModel):
    """Input schema for batch predictions"""
    instances: List[PredictionInput] = Field(..., description="List of instances to predict")


class BatchPredictionOutput(BaseModel):
    """Output schema for batch predictions"""
    predictions: List[PredictionOutput]
    total: int = Field(..., description="Total number of predictions")


def load_models():
    """Load trained models and preprocessing artifacts"""
    global models, preprocessor, label_encoder, feature_names
    
    models_dir = os.getenv('MODELS_DIR', '../models')
    
    try:
        # Load models
        model_files = {
            'xgboost': 'xgboost.pkl',
            'lightgbm': 'lightgbm.pkl',
            'random_forest': 'random_forest.pkl',
            'logistic_regression': 'logistic_regression.pkl'
        }
        
        for name, filename in model_files.items():
            filepath = os.path.join(models_dir, filename)
            if os.path.exists(filepath):
                models[name] = joblib.load(filepath)
                logger.info(f"Loaded model: {name}")
        
        # Load preprocessing artifacts
        preprocessor = joblib.load(os.path.join(models_dir, 'preprocessor.pkl'))
        label_encoder = joblib.load(os.path.join(models_dir, 'label_encoder.pkl'))
        feature_names = joblib.load(os.path.join(models_dir, 'feature_names.pkl'))
        
        logger.info(f"Successfully loaded {len(models)} models")
        return True
    except Exception as e:
        logger.error(f"Error loading models: {str(e)}")
        return False


def preprocess_input(data: Dict[str, Any]) -> np.ndarray:
    """
    Preprocess input data for prediction
    
    Args:
        data: Input data dictionary
    
    Returns:
        Preprocessed feature array
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame([data])
        
        # Handle missing optional fields
        optional_fields = ['day_of_week', 'emp_var_rate', 'cons_price_idx', 
                          'cons_conf_idx', 'euribor3m', 'nr_employed']
        for field in optional_fields:
            if field not in df.columns or df[field].isna().all():
                # Fill with appropriate defaults
                if field == 'day_of_week':
                    df[field] = 'unknown'
                else:
                    df[field] = 0.0  # Will be handled by preprocessing
        
        # Apply feature engineering (simplified version)
        # In production, this should match the exact feature engineering from training
        
        # Transform using saved preprocessor
        X_transformed = preprocessor.transform(df)
        
        return X_transformed
    except Exception as e:
        logger.error(f"Preprocessing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Preprocessing failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    logger.info("Starting Bank Marketing Prediction API...")
    success = load_models()
    if not success:
        logger.warning("Some models failed to load. API may have limited functionality.")
    else:
        logger.info("All models loaded successfully!")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Bank Marketing Prediction API",
        "version": "1.0.0",
        "description": "ML-powered API for predicting term deposit subscription",
        "endpoints": {
            "health": "/health",
            "predict": "/predict",
            "batch_predict": "/batch_predict",
            "models": "/models",
            "metrics": "/metrics"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    model_status = {name: "loaded" for name in models.keys()}
    
    return {
        "status": "healthy" if len(models) > 0 else "degraded",
        "timestamp": datetime.now().isoformat(),
        "models": model_status,
        "preprocessor": "loaded" if preprocessor is not None else "not loaded"
    }


@app.get("/models")
async def list_models():
    """List available models"""
    return {
        "available_models": list(models.keys()),
        "default_model": "xgboost" if "xgboost" in models else list(models.keys())[0] if models else None
    }


@app.post("/predict", response_model=PredictionOutput)
async def predict(
    request: PredictionInput,
    model_name: Optional[str] = "xgboost"
):
    """
    Make a single prediction
    
    Args:
        request: Input features
        model_name: Name of model to use (default: xgboost)
    
    Returns:
        Prediction result with probability
    """
    try:
        # Validate model
        if model_name not in models:
            raise HTTPException(
                status_code=400, 
                detail=f"Model '{model_name}' not found. Available: {list(models.keys())}"
            )
        
        model = models[model_name]
        
        # Preprocess
        with PREDICTION_LATENCY.labels(model_name=model_name).time():
            X = preprocess_input(request.dict())
            
            # Predict
            prediction_proba = model.predict_proba(X)[0]
            prediction_class = model.predict(X)[0]
            
            # Decode prediction
            prediction_label = label_encoder.inverse_transform([prediction_class])[0]
            probability = float(prediction_proba[1])  # Probability of 'yes'
        
        # Update metrics
        PREDICTIONS_COUNTER.labels(
            model_name=model_name, 
            prediction=prediction_label
        ).inc()
        
        return PredictionOutput(
            prediction=prediction_label,
            probability=probability,
            model=model_name,
            timestamp=datetime.now().isoformat(),
            version="1.0.0"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}", exc_info=True)
        ERRORS_COUNTER.labels(error_type="prediction_error").inc()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/batch_predict", response_model=BatchPredictionOutput)
async def batch_predict(
    request: BatchPredictionInput,
    model_name: Optional[str] = "xgboost"
):
    """
    Make batch predictions
    
    Args:
        request: List of input instances
        model_name: Name of model to use
    
    Returns:
        List of predictions
    """
    try:
        predictions = []
        
        for instance in request.instances:
            pred = await predict(instance, model_name)
            predictions.append(pred)
        
        return BatchPredictionOutput(
            predictions=predictions,
            total=len(predictions)
        )
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}", exc_info=True)
        ERRORS_COUNTER.labels(error_type="batch_prediction_error").inc()
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    ERRORS_COUNTER.labels(error_type="unhandled_exception").inc()
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
