import math
from typing import List, Dict, Tuple

def compute_top_k_overlap(baseline_ids: List[str], perturbed_ids: List[str], k: int) -> float:
    """
    Computes the set overlap ratio between baseline Top-K and perturbed Top-K:
    |TopK(baseline) ∩ TopK(perturbed)| / k
    """
    if k <= 0:
        return 0.0
    top_base = set(baseline_ids[:k])
    top_pert = set(perturbed_ids[:k])
    denominator = min(k, len(top_base))
    if denominator == 0:
        return 0.0
    overlap = len(top_base.intersection(top_pert))
    return round(float(overlap) / float(denominator), 4)

def compute_spearman_rank_correlation(baseline_ranks: Dict[str, int], perturbed_ranks: Dict[str, int]) -> float:
    """
    Computes Spearman's rank correlation coefficient rho between baseline and perturbed rankings.
    rho = 1 - (6 * sum(d_i^2)) / (n * (n^2 - 1))
    Where d_i = rank_baseline - rank_perturbed.
    Returns value in [-1.0, 1.0].
    """
    common_ids = [cid for cid in baseline_ranks if cid in perturbed_ranks]
    n = len(common_ids)
    if n <= 1:
        return 1.0

    d_squared_sum = 0.0
    for cid in common_ids:
        d = baseline_ranks[cid] - perturbed_ranks[cid]
        d_squared_sum += (d * d)

    denominator = n * (n * n - 1)
    if denominator == 0:
        return 1.0

    rho = 1.0 - (6.0 * d_squared_sum) / denominator
    return round(max(-1.0, min(1.0, float(rho))), 4)

def compute_rank_displacements(baseline_ranks: Dict[str, int], perturbed_ranks: Dict[str, int]) -> Dict[str, Tuple[int, int]]:
    """
    For each candidate, computes:
    - absolute displacement: |rank_baseline - rank_perturbed|
    - signed displacement: rank_baseline - rank_perturbed (positive means candidate moved up in rank)
    """
    displacements = {}
    for cid, r_base in baseline_ranks.items():
        if cid in perturbed_ranks:
            r_pert = perturbed_ranks[cid]
            abs_disp = abs(r_base - r_pert)
            signed_disp = r_base - r_pert
            displacements[cid] = (abs_disp, signed_disp)
        else:
            displacements[cid] = (0, 0)
    return displacements

def compute_pairwise_flips(baseline_ranks: Dict[str, int], perturbed_ranks: Dict[str, int]) -> int:
    """
    Counts inverted candidate pairs (discordant pairs) between baseline and perturbed rankings.
    A flip occurs when candidate A was ranked higher than B in baseline, but lower in perturbed.
    """
    candidate_ids = list(baseline_ranks.keys())
    n = len(candidate_ids)
    flips = 0

    for i in range(n):
        id_a = candidate_ids[i]
        r_base_a = baseline_ranks[id_a]
        r_pert_a = perturbed_ranks.get(id_a, r_base_a)

        for j in range(i + 1, n):
            id_b = candidate_ids[j]
            r_base_b = baseline_ranks[id_b]
            r_pert_b = perturbed_ranks.get(id_b, r_base_b)

            # Check if order strictly inverted
            if (r_base_a < r_base_b and r_pert_a > r_pert_b) or (r_base_a > r_base_b and r_pert_a < r_pert_b):
                flips += 1

    return flips

def compute_keyword_dependence_index(
    baseline_scores: Dict[str, float],
    masked_scores: Dict[str, float]
) -> float:
    """
    Computes the Keyword Dependence Index (KDI) in [0.0, 1.0].
    Measures the average fractional score degradation when literal keyword tokens are masked.
    - Low KDI (e.g. < 0.25): Strong semantic resilience; candidates retain significant credit from contextual evidence.
    - High KDI (e.g. > 0.60): Heavy reliance on literal lexical keyword overlap.
    """
    if not baseline_scores:
        return 0.0

    ratios = []
    for cid, b_score in baseline_scores.items():
        if b_score > 0.0 and cid in masked_scores:
            m_score = masked_scores[cid]
            loss = max(0.0, b_score - m_score)
            ratios.append(loss / b_score)

    if not ratios:
        return 0.0

    return round(float(sum(ratios) / len(ratios)), 4)
