"""
Feature Dimensionality Reduction for Trading Model

3-Step Strategy:
  1. Variance filtering — remove near-constant features
  2. Correlation analysis — identify redundant feature groups  
  3. Grouped PCA — compress correlated groups, keep standalone features

Usage:
    reducer = FeatureReducer()
    reducer.fit(df, feature_cols)
    df_reduced = reducer.transform(df)
    final_cols = reducer.get_final_columns()
    reducer.save("reducer.pkl")
"""

import numpy as np
import pandas as pd
import pickle
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Optional, Tuple


class FeatureReducer:
    """3-step dimensionality reduction pipeline for trading features.
    
    Step 1: Variance filter — remove features with variance < threshold
    Step 2: Correlation analysis — group features with |r| > correlation_threshold
    Step 3: Grouped PCA — apply PCA to each correlated group, preserve singles
    """
    
    def __init__(
        self,
        variance_threshold: float = 0.01,
        correlation_threshold: float = 0.85,
        pca_components_per_group: int = 3,
        min_group_size: int = 3,
    ):
        """
        Args:
            variance_threshold: Minimum variance to keep a feature (after scaling)
            correlation_threshold: |correlation| above which features are grouped
            pca_components_per_group: Max PCA components per correlated group
            min_group_size: Minimum group size to apply PCA (smaller groups kept as-is)
        """
        self.variance_threshold = variance_threshold
        self.correlation_threshold = correlation_threshold
        self.pca_components_per_group = pca_components_per_group
        self.min_group_size = min_group_size
        
        # Fitted state
        self._fitted = False
        self._variance_mask: Optional[np.ndarray] = None
        self._variance_kept_cols: List[str] = []
        self._correlated_groups: List[List[str]] = []
        self._standalone_cols: List[str] = []
        self._group_pcas: Dict[int, Tuple[PCA, StandardScaler, List[str]]] = {}
        self._final_columns: List[str] = []
    
    def fit(self, df: pd.DataFrame, feature_cols: List[str]) -> 'FeatureReducer':
        """Fit the 3-step reduction pipeline.
        
        Args:
            df: Training DataFrame
            feature_cols: List of feature column names to reduce
            
        Returns:
            self (for chaining)
        """
        X = df[feature_cols].copy()
        
        # Replace inf/nan with 0
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        
        # =====================================================================
        # STEP 1: Variance filtering
        # =====================================================================
        variances = X.var()
        self._variance_mask = variances > self.variance_threshold
        self._variance_kept_cols = [
            col for col, keep in zip(feature_cols, self._variance_mask)
            if keep
        ]
        
        removed_count = len(feature_cols) - len(self._variance_kept_cols)
        if removed_count > 0:
            removed = [col for col, keep in zip(feature_cols, self._variance_mask) if not keep]
            print(f"[FeatureReducer] Step 1: Removed {removed_count} low-variance features: {removed}")
        else:
            print(f"[FeatureReducer] Step 1: All {len(feature_cols)} features passed variance filter")
        
        X_filtered = X[self._variance_kept_cols]
        
        # =====================================================================
        # STEP 2: Correlation analysis
        # =====================================================================
        corr_matrix = X_filtered.corr().abs()
        
        # Find groups of correlated features using union-find
        groups = self._find_correlated_groups(corr_matrix, self._variance_kept_cols)
        
        self._correlated_groups = [g for g in groups if len(g) >= self.min_group_size]
        grouped_cols = set()
        for g in self._correlated_groups:
            grouped_cols.update(g)
        
        self._standalone_cols = [c for c in self._variance_kept_cols if c not in grouped_cols]
        
        print(f"[FeatureReducer] Step 2: Found {len(self._correlated_groups)} correlated groups "
              f"({sum(len(g) for g in self._correlated_groups)} features), "
              f"{len(self._standalone_cols)} standalone features")
        
        for i, group in enumerate(self._correlated_groups):
            print(f"  Group {i}: {group}")
        
        # =====================================================================
        # STEP 3: Grouped PCA
        # =====================================================================
        self._group_pcas = {}
        self._final_columns = list(self._standalone_cols)  # start with standalone
        
        for group_idx, group_cols in enumerate(self._correlated_groups):
            X_group = X_filtered[group_cols].values
            
            # Standardize before PCA
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_group)
            
            # Determine number of components
            n_components = min(self.pca_components_per_group, len(group_cols))
            
            pca = PCA(n_components=n_components)
            pca.fit(X_scaled)
            
            self._group_pcas[group_idx] = (pca, scaler, group_cols)
            
            # Generate PCA column names
            group_name = self._generate_group_name(group_cols)
            for j in range(n_components):
                self._final_columns.append(f"pca_{group_name}_{j}")
            
            explained = sum(pca.explained_variance_ratio_) * 100
            print(f"  Group {group_idx} ({group_name}): {len(group_cols)} features → "
                  f"{n_components} PCA components ({explained:.1f}% variance explained)")
        
        print(f"[FeatureReducer] Step 3: Final feature count: {len(self._final_columns)}")
        self._fitted = True
        return self
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply fitted reduction to new data.
        
        Args:
            df: DataFrame with original feature columns
            
        Returns:
            DataFrame with reduced features
        """
        if not self._fitted:
            raise RuntimeError("FeatureReducer has not been fitted. Call fit() first.")
        
        result = {}
        
        # Copy standalone features
        for col in self._standalone_cols:
            if col in df.columns:
                result[col] = df[col].values
            else:
                result[col] = np.zeros(len(df))
        
        # Transform each PCA group
        for group_idx, (pca, scaler, group_cols) in self._group_pcas.items():
            X_group = df[group_cols].copy()
            X_group = X_group.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            X_scaled = scaler.transform(X_group.values)
            X_pca = pca.transform(X_scaled)
            
            group_name = self._generate_group_name(group_cols)
            for j in range(X_pca.shape[1]):
                result[f"pca_{group_name}_{j}"] = X_pca[:, j]
        
        return pd.DataFrame(result, index=df.index)
    
    def get_final_columns(self) -> List[str]:
        """Return the list of feature column names after reduction."""
        if not self._fitted:
            raise RuntimeError("FeatureReducer has not been fitted. Call fit() first.")
        return list(self._final_columns)
    
    def save(self, path: str):
        """Save fitted reducer to disk."""
        if not self._fitted:
            raise RuntimeError("FeatureReducer has not been fitted. Call fit() first.")
        with open(path, 'wb') as f:
            pickle.dump(self, f)
        print(f"[FeatureReducer] Saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'FeatureReducer':
        """Load a fitted reducer from disk."""
        with open(path, 'rb') as f:
            reducer = pickle.load(f)
        if not isinstance(reducer, cls):
            raise TypeError(f"Expected FeatureReducer, got {type(reducer)}")
        print(f"[FeatureReducer] Loaded from {path} ({len(reducer._final_columns)} features)")
        return reducer
    
    def _find_correlated_groups(
        self, corr_matrix: pd.DataFrame, cols: List[str]
    ) -> List[List[str]]:
        """Find groups of correlated features using union-find."""
        parent = {col: col for col in cols}
        
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Union features with |corr| > threshold
        for i, col_a in enumerate(cols):
            for j, col_b in enumerate(cols):
                if i < j and corr_matrix.loc[col_a, col_b] > self.correlation_threshold:
                    union(col_a, col_b)
        
        # Group by root
        groups_dict: Dict[str, List[str]] = {}
        for col in cols:
            root = find(col)
            groups_dict.setdefault(root, []).append(col)
        
        # Only return groups with > 1 member
        return [g for g in groups_dict.values() if len(g) > 1]
    
    @staticmethod
    def _generate_group_name(group_cols: List[str]) -> str:
        """Generate a short name for a PCA group based on its feature names."""
        # Find common prefix
        if not group_cols:
            return "unknown"
        
        # Try to find a meaningful common substring
        prefixes = set()
        for col in group_cols:
            parts = col.split("_")
            if len(parts) >= 2:
                prefixes.add(parts[0])
            else:
                prefixes.add(col[:4])
        
        if len(prefixes) == 1:
            return list(prefixes)[0]
        
        # Use first 3 chars of first column as fallback
        return group_cols[0][:8].replace("_", "")
