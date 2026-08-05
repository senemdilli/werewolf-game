"""
Standalone Script to compute phase Alignment Trust averages for Human Truth and LLMs (currently Qwen, Gemma, and maybe Mistral) across games and experiments (A, B, etc.)
"""

from pathlib import Path
import json
import sys
from typing import Dict, List

def compute_alignment_trust_by_phase(model_dir: Path) -> Dict[int, float]:
    phases = {}
    if not model_dir.exists():
        return {}
    
    for p in model_dir.glob('*.json'):
        if p.name.endswith('-trace.md'):
            continue
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
            
        obs = data.get('player_name')
        for phase in data.get('phases', []):
            p_idx = phase.get('phase_idx')
            if p_idx is None:
                continue
            if p_idx not in phases:
                phases[p_idx] = []
            labels = phase.get('labels', {})
            if isinstance(labels, dict):
                for target, dims in labels.items():
                    if obs != target and isinstance(dims, dict) and 'alignment' in dims:
                        align = dims.get('alignment')
                        if isinstance(align, dict):
                            score = align.get('trust')
                            if score is not None:
                                phases[p_idx].append(score)
                                
    return {k: round(sum(v) / len(v), 2) for k, v in sorted(phases.items()) if len(v) > 0}


def main():
    game_sub = sys.argv[1] if len(sys.argv) > 1 else '5NOHGS'
    
    candidates = [
        Path('../results/llm-labeling'),
        Path('results/llm-labeling'),
        Path('../../results/llm-labeling')
    ]
    base_dir = None
    for cand in candidates:
        if cand.exists():
            base_dir = cand
            break
            
    if not base_dir:
        print("Error: Could not find results/llm-labeling directory.")
        return

    exp_a_dirs = list((base_dir / "a").glob(f"*{game_sub}*"))
    exp_b_dirs = list((base_dir / "b").glob(f"*{game_sub}*"))
    
    cols = {}
    
    if exp_a_dirs:
        g_a = exp_a_dirs[0]
        cols['Qwen (A)'] = compute_alignment_trust_by_phase(g_a / 'qwen3.6-35b')
        cols['Gemma (A)'] = compute_alignment_trust_by_phase(g_a / 'gemma4-31b')
        cols['Mistral (A)'] = compute_alignment_trust_by_phase(g_a / 'mistral-large-123b')
        
    if exp_b_dirs:
        g_b = exp_b_dirs[0]
        cols['Qwen (B)'] = compute_alignment_trust_by_phase(g_b / 'qwen3.6-35b')
        cols['Gemma (B)'] = compute_alignment_trust_by_phase(g_b / 'gemma4-31b')
        cols['Mistral (B)'] = compute_alignment_trust_by_phase(g_b / 'mistral-large-123b')

    all_phases = sorted(set(p for res in cols.values() for p in res.keys()))
    col_names = list(cols.keys())
    
    print(f"ALIGNMENT TRUST EVALUATION FOR GAME: {game_sub}")
    
    # Header
    header_str = f"{'Phase':<8}" + "".join(f"{name:>13}" for name in col_names)
    print(header_str)
    print("-" * len(header_str))
    
    # Rows
    for p in all_phases:
        row_str = f"{p:<8}"
        for name in col_names:
            val = cols[name].get(p)
            row_str += f"{val:>13.2f}" if val is not None else f"{'N/A':>13}"
        print(row_str)
        
    print("-" * len(header_str))
    
    # Means
    mean_str = f"{'Mean':<8}"
    for name in col_names:
        vals = list(cols[name].values())
        if vals:
            m_val = round(sum(vals) / len(vals), 2)
            mean_str += f"{m_val:>13.2f}"
        else:
            mean_str += f"{'N/A':>13}"
    print(mean_str)

if __name__ == '__main__':
    main()
