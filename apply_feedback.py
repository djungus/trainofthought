import json
import os
import sys

def main():
    f_type = os.environ.get("FEEDBACK_TYPE")
    target = os.environ.get("FEEDBACK_TARGET")
    feedback = os.environ.get("FEEDBACK_VAL")
    
    if not f_type or not target or not feedback:
        print("Error: Missing feedback env variables (FEEDBACK_TYPE, FEEDBACK_TARGET, FEEDBACK_VAL).")
        sys.exit(1)
        
    f_type = f_type.strip()
    target = target.strip()
    feedback = feedback.strip().lower()
    
    print(f"Received feedback: type={f_type}, target={target}, value={feedback}")
    
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        print(f"Error: config.json not found at {config_path}")
        sys.exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    user_conf = config.setdefault("user", {})
    weights = user_conf.setdefault("weights", {})
    
    # Determine the weights dictionary sub-key ('interests' or 'authors')
    weight_group_key = "interests" if f_type == "interest" else "authors"
    group_dict = weights.setdefault(weight_group_key, {})
    
    # Get current weight, default to 1.0 if not set
    current_weight = group_dict.get(target, 1.0)
    
    # Apply weight adjustment (+0.1 for positive, -0.1 for negative)
    adjustment = 0.1 if feedback == "yes" else -0.1
    new_weight = round(current_weight + adjustment, 1)
    
    # Clamp weight between 0.2 and 2.0
    new_weight = max(0.2, min(2.0, new_weight))
    
    group_dict[target] = new_weight
    print(f"Success: Updated {f_type} '{target}' weight from {current_weight} to {new_weight}")
    
    # Save back to config.json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        
    print("config.json saved successfully.")

if __name__ == "__main__":
    main()
