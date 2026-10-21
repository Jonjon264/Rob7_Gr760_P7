from sentence_transformers import SentenceTransformer, util
import json

model = SentenceTransformer("all-MiniLM-L6-v2") 
#all-MiniLM-L6-v2 is a very lightweight model




def readWaypoints():
    labels = []
    waypoints = []
    with open("/root/waypoints.json", "r") as json_file:
        json_data = json.load(json_file)
    for wp in json_data:
        waypoint = [wp["name"],wp["descriptor"],wp["x"],wp["y"]] #Makes each waypoint an array of [name,descriptor,x,y]
        waypoints.append(waypoint)
        labels.append(f'{wp["name"]}: {wp["descriptor"]}')
    return labels, waypoints

#List of target labels:
#labels = ["Robotic Workstation", "tooldesk"]
labels, waypoints = readWaypoints()

# Pre-compute embeddings for your fixed list of labels
label_embeddings = model.encode(labels, convert_to_tensor=True)


    


    

def find_best_label(command: str, score_threshold: float = 0.4):
    # Encode the input command
    command_embedding = model.encode(command, convert_to_tensor=True)
    
    # Calculate cosine similarity against all candidate labels
    cosine_scores = util.cos_sim(command_embedding, label_embeddings)[0]
    
    # Find the label with the highest score
    best_idx = cosine_scores.argmax().item()
    best_score = cosine_scores[best_idx].item()
    
    if best_score < score_threshold:
        return None, best_score  # Command didn't match any target closely enough
        
    return labels[best_idx], best_score, best_idx


# Example Usage    print(best_idx)
commands = [
    "Head over to the tool station",
    "Go to the charging station",
]

readWaypoints()
for cmd in commands:
    matched_label, score, id = find_best_label(cmd)
 #   print(f"Command: '{cmd}' -> Matched: '{matched_label}' (Score: {score:.3f})")
    print(f"Command: '{cmd}' -> Matched: '{waypoints[id][0]}' (Score: {score:.3f}) Coords(x,y): {[waypoints[id][2],waypoints[id][3]]}")
