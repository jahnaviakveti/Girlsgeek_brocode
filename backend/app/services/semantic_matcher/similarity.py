import numpy as np

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Calculate the cosine similarity between two 1D NumPy arrays safely.
    Returns 0.0 if either vector is empty or a zero vector.
    """
    if vec_a.size == 0 or vec_b.size == 0:
        return 0.0
        
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
        
    similarity = np.dot(vec_a, vec_b) / (norm_a * norm_b)
    # Clip to avoid floating point issues exceeding [-1.0, 1.0]
    return float(np.clip(similarity, -1.0, 1.0))

def batch_cosine_similarity(vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Calculate cosine similarity between a 1D vector (D,) and a 2D matrix (N, D).
    Returns a 1D NumPy array of similarities of shape (N,).
    """
    if vec.size == 0 or matrix.size == 0:
        return np.array([])
    if matrix.ndim == 1:
        return np.array([cosine_similarity(vec, matrix)])
        
    norm_vec = np.linalg.norm(vec)
    if norm_vec == 0.0:
        return np.zeros(matrix.shape[0], dtype=float)
        
    norm_matrix = np.linalg.norm(matrix, axis=1)
    zero_mask = norm_matrix == 0.0
    safe_norm_matrix = np.where(zero_mask, 1.0, norm_matrix)
    
    dots = np.dot(matrix, vec)
    sims = dots / (safe_norm_matrix * norm_vec)
    sims[zero_mask] = 0.0
    return np.clip(sims, -1.0, 1.0)
