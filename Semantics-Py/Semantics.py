from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2") 
#all-MiniLM-L6-v2 is a very lightweight model

#List of target labels:
labels = ["Robotic Workstation", "tooldesk"]

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
        
    return labels[best_idx], best_score



# Example Usage
commands = [
    "Head over to the tool station",
    "Go to the robotic workstation"
]

for cmd in commands:
    matched_label, score = find_best_label(cmd)
    print(f"Command: '{cmd}' -> Matched: '{matched_label}' (Score: {score:.3f})")
