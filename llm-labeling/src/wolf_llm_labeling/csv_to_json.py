import argparse
import glob
import json
import os
import sys
from pathlib import Path

src_dir = Path(__file__).parents[1]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from wolf_llm_labeling.game_records import GameRecord
from wolf_llm_labeling.models import (
    Message,
    SystemMessage,
    Vote,
    KillEvent,
    ExileEvent,
    MayorElected,
    SeerRevealed,
    WitchKilled,
    WitchSaved,
)

def convert_game_to_dict(record: GameRecord, game_file: str, room_code: str | None = None) -> dict:
    data = {
      "game_id": record.get_game_id(),
      "game_file": game_file,
      "room_code": room_code,
      "winner": record.get_winner(),
      "players": {p: r.value for p, r in record.get_players().items()},
      "phases": []
    }
    
    for phase_idx in range(record.get_phase_count()):
        phase_type = record.get_phase_type(phase_idx)
        phase_data = record.get_phase_data(phase_idx)
        day_num = (phase_idx // 3) + 1
        
        events = []
        for item in phase_data:
            event_type = type(item).__name__
            item_dict = {"type": event_type}
            
            if isinstance(item, Message):
                item_dict.update({
                    "player_name": item.player_name,
                    "forum": item.forum.value,
                    "message": item.message
                })
            elif isinstance(item, SystemMessage):
                item_dict["message"] = item.message
            elif isinstance(item, Vote):
                item_dict.update({
                    "player_name": item.player_name,
                    "voted_for": item.voted_for,
                    "reason": item.reason.value
                })
            elif isinstance(item, KillEvent):
                item_dict["affected_player"] = item.affected_player
            elif isinstance(item, ExileEvent):
                item_dict["affected_player"] = item.affected_player
            elif isinstance(item, MayorElected):
                item_dict["affected_player"] = item.affected_player
            elif isinstance(item, SeerRevealed):
                item_dict["affected_player"] = item.affected_player
            elif isinstance(item, WitchKilled):
                item_dict["affected_player"] = item.affected_player
            elif isinstance(item, WitchSaved):
                item_dict["affected_player"] = item.affected_player
                
            if hasattr(item, "timestamp") and item.timestamp:
                item_dict["timestamp"] = item.timestamp
                
            events.append(item_dict)
            
        data["phases"].append({
            "phase_idx": phase_idx,
            "phase_type": phase_type.value,
            "day": day_num,
            "events": events
        })
        
    return data

def main():
    parser = argparse.ArgumentParser(description="CSV to JSON converter")
    parser.add_argument("path", type=str, help="CSV file path, directory path, or glob pattern")
    parser.add_argument("--output-dir", type=str, help="Directory to save JSON output files")
    
    args = parser.parse_args()
    
    if os.path.isdir(args.path):
        csv_files = glob.glob(os.path.join(args.path, "game-*.csv"))
    elif "*" in args.path:
        csv_files = glob.glob(args.path)
    else:
        csv_files = [args.path]
        
    for csv_path in csv_files:
        csv_path_obj = Path(csv_path)
        json_labels_path = csv_path_obj.with_name(csv_path_obj.name.replace(".csv", "-labels.json"))
        
        room_code = None
        record = GameRecord()
        if json_labels_path.exists():
            record.read_from_files([str(json_labels_path), csv_path])
            try:
                with open(json_labels_path, "r", encoding="utf-8") as lf:
                    labels_data = json.load(lf)
                    room_code = labels_data.get("room_code")
            except Exception:
                pass
        else:
            record.read_from_files(csv_path)
            
        game_file = csv_path_obj.name.replace(".csv", "")
        game_dict = convert_game_to_dict(record, game_file=game_file, room_code=room_code)
        
        out_dir = Path(args.output_dir) if args.output_dir else csv_path_obj.parent / "converted"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        out_file = out_dir / csv_path_obj.name.replace(".csv", "-converted-grouped.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(game_dict, f, indent=2)
            
        print(f"Converted {csv_path_obj.name} to {out_file.name}")

if __name__ == "__main__":
    main()
