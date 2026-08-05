"""
Standalone Script to compute phase Alignment Trust averages for Human Truth and LLMs (currently Qwen, Gemma, and maybe Mistral) across games and experiments (A, B, etc.)
"""

from pathlib import Path
import json
import sys
import argparse
from typing import Dict, List

def compute_human_alignment_trust_dynamic(game_sub: str, game_records_dir: Path) -> Dict[int, float]:
    """Parse human labels"""
    if not game_records_dir.exists():
        return {}

    files = list(game_records_dir.glob(f"*{game_sub}*-labels.json"))
    if not files:
        files = list(game_records_dir.glob(f"*{game_sub}*.json"))
        files = [f for f in files if f.name.endswith('-labels.json')]
    if not files:
        return {}
        
    try:
        with open(files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {}
        
    cp_list = []
    for r in data.get('rounds', []):
        for cp in r.get('checkpoints', []):
            cp_list.append(cp)
            
    pair_scores_per_cp = []
    all_pairs = set()
    
    for cp in cp_list:
        cp_dict = {}
        for label_block in cp.get('labels', []):
            obs = label_block.get('observer', {}).get('name')
            for t_item in label_block.get('targets', []):
                t_name = t_item.get('player', {}).get('name')
                align = t_item.get('alignment', {})
                score = align.get('score') if isinstance(align, dict) else None
                if obs and t_name and obs != t_name and score is not None:
                    pair_key = (obs, t_name)
                    cp_dict[pair_key] = score
                    all_pairs.add(pair_key)
        pair_scores_per_cp.append(cp_dict)

    if not all_pairs:
        return {}

    phase_pair_scores = {0: {pair: 4.0 for pair in all_pairs}}
    pair_last = {pair: 4.0 for pair in all_pairs}
    
    for cp_idx, cp_dict in enumerate(pair_scores_per_cp, start=1):
        p_idx = min(cp_idx, 6)
        for pair in all_pairs:
            if pair in cp_dict:
                pair_last[pair] = cp_dict[pair]
        phase_pair_scores[p_idx] = dict(pair_last)

    for p in range(len(pair_scores_per_cp) + 1, 7):
        phase_pair_scores[p] = dict(pair_last)
        
    phase_means = {}
    for p in range(0, 7):
        p_vals = list(phase_pair_scores[p].values())
        phase_means[p] = round(sum(p_vals) / len(p_vals), 2) if p_vals else 4.00
        
    return phase_means


def compute_alignment_trust_by_phase(model_dir: Path) -> Dict[int, float]:
    """Parse JSON run files in model_dir and return phase_idx -> average alignment trust"""
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
    parser = argparse.ArgumentParser(description="Compute Phase-by-Phase Alignment Trust")
    parser.add_argument("game", nargs="?", default="5NOHGS", help="Game ID or substring (e.g. 5NOHGS, UBY0T7)")
    parser.add_argument("-e", "--experiments", nargs="+", help="Limit to specific experiment letters (e.g. a b or d e f)")
    args = parser.parse_args()

    game_sub = args.game
    target_exps = [e.lower() for e in args.experiments] if args.experiments else None
    
    # Locate base results directory
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

    # Locate game records directory
    rec_candidates = [
        Path('../results/game-records'),
        Path('results/game-records'),
        Path('../../results/game-records')
    ]
    rec_dir = None
    for r_cand in rec_candidates:
        if r_cand.exists():
            rec_dir = r_cand
            break

    cols = {}
    
    # Compute Human Ground Truth from game-records
    if rec_dir:
        human_scores = compute_human_alignment_trust_dynamic(game_sub, rec_dir)
        if human_scores:
            cols['Human'] = human_scores
            
    # Discover experiment directories + Filter
    for exp_dir in sorted(base_dir.iterdir()):
        if exp_dir.is_dir():
            exp_name_lower = exp_dir.name.lower()
            if target_exps and exp_name_lower not in target_exps:
                continue
                
            exp_letter = exp_dir.name.upper()
            game_folders = list(exp_dir.glob(f"*{game_sub}*"))
            if game_folders:
                g_path = game_folders[0]
                for model_dir in sorted(g_path.iterdir()):
                    if model_dir.is_dir():
                        m_name = model_dir.name
                        disp_name = f"{m_name} ({exp_letter})"
                        if 'qwen' in m_name.lower():
                            disp_name = f"Qwen ({exp_letter})"
                        elif 'gemma' in m_name.lower():
                            disp_name = f"Gemma ({exp_letter})"
                        elif 'mistral' in m_name.lower():
                            disp_name = f"Mistral ({exp_letter})"
                            
                        scores = compute_alignment_trust_by_phase(model_dir)
                        if scores:
                            cols[disp_name] = scores

    if not cols:
        print(f"No results found for game pattern: {game_sub}")
        return

    all_phases = sorted(set(p for res in cols.values() for p in res.keys()))
    
    # Forward-fill Human column
    if 'Human' in cols and cols['Human']:
        max_h_p = max(cols['Human'].keys())
        last_h_val = cols['Human'][max_h_p]
        for p in all_phases:
            if p not in cols['Human']:
                cols['Human'][p] = last_h_val

    col_names = list(cols.keys())
    
    print(f"##### ALIGNMENT TRUST EVALUATION FOR GAME: {game_sub} #####")
    
    # Header
    header_str = f"{'Phase':<8}" + "".join(f"{name:>13}" for name in col_names)
    print(header_str)
    print("_" * len(header_str))
    
    # Rows
    for p in all_phases:
        row_str = f"{p:<8}"
        for name in col_names:
            val = cols[name].get(p)
            row_str += f"{val:>13.2f}" if val is not None else f"{'N/A':>13}"
        print(row_str)
        
    print("_" * len(header_str))
    
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
