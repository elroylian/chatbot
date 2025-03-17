import pandas as pd
import json
import re

# Load the dataset
df = pd.read_csv('intermediate_graded_evaluation_results.csv',encoding='latin-1')

# Identify rows with JSON parsing errors
error_mask = df['grading_feedback'].str.contains('JSON parsing error', na=False)
error_rows = df[error_mask]

def extract_json_from_text(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        matches = re.findall(r'```json(.*?)```', text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    return None

# Process rows with JSON errors
for idx, row in error_rows.iterrows():
    extracted_json = extract_json_from_text(row['grading_feedback'])
    
    if extracted_json:
        try:
            model1_total = extracted_json["model1_score"]["total"]
            model2_total = extracted_json["model2_score"]["total"]
            winner = extracted_json.get('winner', 'tie')

            # Update grading score and winner
            df.at[idx, 'grading_score'] = f"Chatbot: {model1_total}/25, GPT4o: {model2_total}/25"
            df.at[idx, 'winner'] = winner

            # Optionally, store cleaned JSON explicitly
            df.at[idx, 'grading_feedback'] = json.dumps(extracted_json)

        except KeyError as e:
            print(f"Key missing at row {idx}: {e}")
    else:
        print(f"JSON extraction still failing at row {idx}")

# Save cleaned dataset
df.to_csv('graded_evaluation_results_cleaned.csv', index=False)

# Verify if any JSON errors remain
remaining_errors = df[df['grading_feedback'].str.contains('JSON parsing error', na=False)]
print(f"Remaining errors after cleaning: {len(remaining_errors)}")
