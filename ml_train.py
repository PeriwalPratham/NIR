import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib  # Replace 'import pickle'
import os

def engineer_features(X_raw):
    """
    Transforms raw spectroscopy channels into relational features 
    to capture the 'shape' of the material reflection curve.
    """
    X_eng = pd.DataFrame(index=X_raw.index)
    raw_channels = ['R', 'S', 'T', 'U', 'V', 'W']
    
    # 1. Retain the original raw values
    for col in raw_channels:
        X_eng[col] = X_raw[col]
    
    # 2. Total Spectral Footprint Intensity
    X_eng['Total_Intensity'] = X_raw[raw_channels].sum(axis=1).replace(0, 1)
    
    # 3. Normalized Curves (Ratios relative to total brightness)
    for col in raw_channels:
        X_eng[f'{col}_norm'] = X_raw[col] / X_eng['Total_Intensity']
        
    # 4. Spectral Gradients (Slopes between consecutive sensor channels)
    X_eng['R_S_diff'] = X_raw['R'] - X_raw['S']
    X_eng['S_T_diff'] = X_raw['S'] - X_raw['T']
    X_eng['T_U_diff'] = X_raw['T'] - X_raw['U']
    X_eng['U_V_diff'] = X_raw['U'] - X_raw['V']
    X_eng['V_W_diff'] = X_raw['V'] - X_raw['W']
    
    # 5. Row-wise Statistical Profiles
    X_eng['Spectral_Mean'] = X_raw[raw_channels].mean(axis=1)
    X_eng['Spectral_Std'] = X_raw[raw_channels].std(axis=1)
    X_eng['Spectral_Max'] = X_raw[raw_channels].max(axis=1)
    
    return X_eng

def train_spectroscopy_model(data_path, model_output_path):
    if not os.path.exists(data_path):
        print(f"Error: Dataset not found at {data_path}")
        return

    print("Loading master dataset...")
    df = pd.read_csv(data_path)
    
    # ==============================================================================
    # LABEL CONSOLIDATION & FILTERING
    # ==============================================================================
    # 1. Force strings to uppercase to avoid mismatching casing differences
    df['material_type'] = df['material_type'].astype(str).str.upper().str.strip()
    
    # 2. Convert all variations of paper directly into wood
    df['material_type'] = df['material_type'].replace(['PAPER'], 'WOOD')
    
    # 3. Strict class matching: Only keep WOOD, METAL, and PLASTIC
    allowed_materials = ['WOOD', 'METAL', 'PLASTIC']
    df = df[df['material_type'].isin(allowed_materials)]
    
    # Isolate initial baseline features (No temperature column present in this file)
    base_features = ['R', 'S', 'T', 'U', 'V', 'W']
    X_raw = df[base_features].copy().apply(pd.to_numeric, errors='coerce')
    y = df['material_type'].copy()
    
    # Clean rows containing any broken data points
    valid_indices = X_raw.notna().all(axis=1)
    X_raw = X_raw[valid_indices]
    y = y[valid_indices]
    
    # Run the Feature Engineering Pipeline
    X = engineer_features(X_raw)

    print(f"Dataset cleaned and mapped successfully. Rows remaining: {len(X)}")
    print(f"Target classes to predict: {y.unique()}")
    print("Initial class distribution:\n", y.value_counts())

    if len(X) == 0:
        print("Error: No data left after filtering.")
        return

    # Train/Test split (stratified to ensure even class representations in test set)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # ==============================================================================
    # TRAINING OVERSAMPLING PIPELINE
    # ==============================================================================
    X_train_df = pd.DataFrame(X_train)
    X_train_df['target_label'] = y_train
    
    # Split training partition by target class
    df_wood = X_train_df[X_train_df['target_label'] == 'WOOD']
    df_plastic = X_train_df[X_train_df['target_label'] == 'PLASTIC']
    df_metal = X_train_df[X_train_df['target_label'] == 'METAL']
    
    # Determine target size based on the majority class among WOOD and PLASTIC
    majority_class_size = max(len(df_wood), len(df_plastic))
    
    if len(df_metal) > 0 and len(df_metal) < majority_class_size:
        print(f"\n[Oversampling] Duplicating 'METAL' samples from {len(df_metal)} up to {majority_class_size}...")
        df_metal_oversampled = df_metal.sample(majority_class_size, replace=True, random_state=42)
        
        # Combine balanced datasets back together
        X_train_balanced = pd.concat([df_wood, df_plastic, df_metal_oversampled])
        
        X_train = X_train_balanced.drop(columns=['target_label'])
        y_train = X_train_balanced['target_label']
        print("Balanced training class distribution:\n", y_train.value_counts())
    else:
        X_train = X_train_df.drop(columns=['target_label'])

    # ==============================================================================
    # CLASSIFIER TRAINING
    # ==============================================================================
    print("\nTraining Random Forest Classifier on Balanced Engineered Dataset...")
    model = RandomForestClassifier(n_estimators=150, random_state=42)
    model.fit(X_train, y_train)
    print("Model compilation complete!")
    
    # Validation scoring report
    y_pred = model.predict(X_test)
    print("\n================ MODEL PERFORMANCE ================")
    print(classification_report(y_test, y_pred))
    print("===================================================\n")
    
    # Export trained asset
    with open(model_output_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model file successfully saved to: {model_output_path}")

if __name__ == "__main__":
    # Change these paths if your file directories change
    DATASET_PATH = '/home/pratham/Arduino/spectrography/transformed_master_dataset_no_rubber.csv'
    MODEL_PATH = '/home/pratham/Arduino/spectrography/spectroscopy_model.pkl'
    joblib.dump(MODEL_PATH,DATASET_PATH  )
    print(f"Model file successfully saved to: {"/home/pratham/Arduino/spectrography/spectroscopy_model.pkl"}")
    
    train_spectroscopy_model(DATASET_PATH, MODEL_PATH)
