import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import json
from matplotlib.gridspec import GridSpec
import os

# Set the user level - change this to 'beginner', 'intermediate', or 'advanced'
LEVEL = 'intermediate'

# Map of category field names for each level
CATEGORY_FIELDS = {
    'beginner': {
        "technical_accuracy": "Technical Accuracy",
        "beginner_accessibility": "Beginner Accessibility", 
        "clarity_examples": "Clarity & Examples",
        "educational_value": "Educational Value",
        "practical_application": "Practical Application"
    },
    'intermediate': {
        "technical_accuracy_depth": "Technical Accuracy & Depth",
        "implementation_focus": "Implementation Focus",
        "algorithmic_analysis": "Algorithmic Analysis",
        "conceptual_connections": "Conceptual Connections",
        "progressive_advancement": "Progressive Advancement"
    },
    'advanced': {
        "technical_sophistication": "Technical Sophistication",
        "optimization_insight": "Optimization Insight",
        "complexity_analysis": "Complexity Analysis",
        "system_level_integration": "System-Level Integration",
        "research_connections": "Research Connections"
    }
}

# Load the graded results
df = pd.read_csv(f'{LEVEL}_graded_evaluation_results.csv', encoding='latin-1', on_bad_lines='skip')

# Create a directory for the visualizations
os.makedirs(f'evaluation_results/{LEVEL}', exist_ok=True)

# Auto-detect the correct field names from the data
def detect_field_names():
    """Automatically detect the field names in the evaluation data."""
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                # Get the keys from model1_score
                return list(data["model1_score"].keys())
            except:
                continue
    
    # If we can't detect from data, use the predefined mapping
    return list(CATEGORY_FIELDS[LEVEL].keys())

# Get the field names
detected_fields = detect_field_names()
print(f"Detected fields: {detected_fields}")

# Remove 'total' if it exists, as we handle it separately
if 'total' in detected_fields:
    detected_fields.remove('total')

# 1. Overall Win Comparison (Bar Chart)
def plot_win_comparison():
    # Count the wins for each model
    win_counts = df['winner'].value_counts().reindex(['model1', 'model2', 'tie'], fill_value=0)
    
    # Rename for display
    win_counts.index = ['Your Chatbot', 'GPT-4o-mini', 'Tie']
    
    # Calculate percentages
    total = win_counts.sum()
    percentages = (win_counts / total * 100).round(1)
    
    # Create the plot
    plt.figure(figsize=(10, 6))
    ax = win_counts.plot(kind='bar', color=['#4CAF50', '#2196F3', '#9E9E9E'])
    
    plt.title(f'Overall Performance Comparison ({LEVEL.capitalize()} Level)', fontsize=16, pad=20)
    plt.ylabel('Number of Wins', fontsize=14)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add count and percentage labels on bars
    for i, (count, percentage) in enumerate(zip(win_counts, percentages)):
        ax.text(i, count + 0.3, f"{count} ({percentage}%)", 
                ha='center', fontsize=12, fontweight='bold')
    
    plt.ylim(0, max(win_counts) * 1.2)  # Add space for labels
    plt.tight_layout()
    plt.savefig(f'evaluation_results/{LEVEL}/win_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return win_counts, percentages

# 2. Score Breakdown by Category
def plot_category_scores():
    # Initialize score dictionaries based on detected fields
    model1_scores = {field: [] for field in detected_fields}
    model2_scores = {field: [] for field in detected_fields}
    
    # Extract scores from JSON feedback
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                for field in detected_fields:
                    if field in data["model1_score"]:
                        model1_scores[field].append(data["model1_score"][field])
                    
                    if field in data["model2_score"]:
                        model2_scores[field].append(data["model2_score"][field])
            except:
                continue
    
    # Calculate averages for each category
    model1_avgs = {cat: round(sum(scores)/len(scores), 5) if scores else 0 
                    for cat, scores in model1_scores.items()}
    model2_avgs = {cat: round(sum(scores)/len(scores), 5) if scores else 0 
                    for cat, scores in model2_scores.items()}
    
    # Get category display names
    if LEVEL in CATEGORY_FIELDS:
        category_display = [CATEGORY_FIELDS[LEVEL].get(field, field.replace('_', ' ').title()) 
                           for field in detected_fields]
    else:
        category_display = [field.replace('_', ' ').title() for field in detected_fields]
    
    # Make results dataframe
    results_df = pd.DataFrame({
        'Category': category_display,
        'Your Chatbot': list(model1_avgs.values()),
        'GPT-4o-mini': list(model2_avgs.values())
    })
    
    # Radar chart
    categories = results_df['Category']
    
    # Create figure and polar axis
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, polar=True)
    
    # Number of categories
    N = len(categories)
    
    # Angle of each category
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Close the loop
    
    # Get scores
    model1_scores = results_df['Your Chatbot'].values.tolist()
    model2_scores = results_df['GPT-4o-mini'].values.tolist()
    
    # Add closure
    model1_scores += model1_scores[:1]
    model2_scores += model2_scores[:1]
    
    # Draw the polygon and fill area
    ax.plot(angles, model1_scores, 'o-', linewidth=2, label='Your Chatbot', color='#4CAF50')
    ax.fill(angles, model1_scores, alpha=0.25, color='#4CAF50')
    
    ax.plot(angles, model2_scores, 'o-', linewidth=2, label='GPT-4o-mini', color='#2196F3')
    ax.fill(angles, model2_scores, alpha=0.25, color='#2196F3')
    
    # Set category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=12)
    
    # Set y-axis limits
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    
    # Add legend
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1), fontsize=12)
    
    plt.title(f'Average Scores by Category for {LEVEL.capitalize()} Users', fontsize=16, y=1.08)
    plt.tight_layout()
    plt.savefig(f'evaluation_results/{LEVEL}/category_radar.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # Also create a bar chart version for clarity
    plt.figure(figsize=(12, 6))
    
    # Set the positions and width for the bars
    pos = list(range(len(categories)))
    width = 0.35
    
    # Create the bars
    plt.bar([p - width/2 for p in pos], model1_scores[:-1], width, 
            alpha=0.8, color='#4CAF50', label='Your Chatbot')
    
    plt.bar([p + width/2 for p in pos], model2_scores[:-1], width, 
            alpha=0.8, color='#2196F3', label='GPT-4o-mini')
    
    # Set axes and labels
    plt.axhline(y=3, linestyle='--', color='gray', alpha=0.5)  # Add reference line at score 3
    plt.ylabel('Average Score (0-5)', fontsize=14)
    plt.title(f'Average Category Scores for {LEVEL.capitalize()} Users', fontsize=16, pad=20)
    plt.xticks(pos, categories, fontsize=11, rotation=30, ha='right')
    plt.yticks(range(6))
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Add value labels on the bars
    for i, v in enumerate(model1_scores[:-1]):
        plt.text(i - width/2, v + 0.1, f"{v:.1f}", ha='center', fontsize=10)
    
    for i, v in enumerate(model2_scores[:-1]):
        plt.text(i + width/2, v + 0.1, f"{v:.1f}", ha='center', fontsize=10)
    
    plt.legend(fontsize=12)
    plt.ylim(0, 5.5)  # Add space for labels
    plt.tight_layout()
    plt.savefig(f'evaluation_results/{LEVEL}/category_bars.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return results_df

# 3. Total Score Distribution
def plot_score_distribution():
    # Extract total scores
    model1_totals = []
    model2_totals = []
    
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                if "total" in data["model1_score"]:
                    model1_totals.append(data["model1_score"]["total"])
                
                if "total" in data["model2_score"]:
                    model2_totals.append(data["model2_score"]["total"])
            except:
                continue
    
    # Create a DataFrame for the box plot
    scores_df = pd.DataFrame({
        'Your Chatbot': model1_totals,
        'GPT-4o-mini': model2_totals
    })
    
    # Create the plot
    plt.figure(figsize=(10, 6))
    
    # Boxplot
    sns.boxplot(data=scores_df, palette=['#4CAF50', '#2196F3'])
    
    # Add strip plot for individual points
    sns.stripplot(data=scores_df, color='black', alpha=0.5, jitter=True)
    
    # Add mean values as text
    for i, col in enumerate(scores_df.columns):
        mean_val = scores_df[col].mean()
        plt.text(i, scores_df[col].max() + 0.5, f'Mean: {mean_val:.1f}', 
                 ha='center', fontsize=11, fontweight='bold')
    
    plt.title(f'Distribution of Total Scores for {LEVEL.capitalize()} Level (Out of 25)', fontsize=16, pad=20)
    plt.ylabel('Total Score', fontsize=14)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.ylim(0, 25.5)  # Set y-axis limit to maximum possible score
    plt.tight_layout()
    plt.savefig(f'evaluation_results/{LEVEL}/score_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return scores_df


# 4. Create a comprehensive dashboard
def create_evaluation_dashboard():
    # Create a figure with subplots
    fig = plt.figure(figsize=(20, 24))
    gs = GridSpec(3, 2, figure=fig)
    
    # 1. Win comparison (top left)
    win_counts = df['winner'].value_counts().reindex(['model1', 'model2', 'tie'], fill_value=0)
    win_counts.index = ['Your Chatbot', 'GPT-4o-mini', 'Tie']
    total = win_counts.sum()
    percentages = (win_counts / total * 100).round(1)
    
    ax1 = fig.add_subplot(gs[0, 0])
    win_counts.plot(kind='bar', color=['#4CAF50', '#2196F3', '#9E9E9E'], ax=ax1)
    ax1.set_title('Overall Performance Comparison', fontsize=16)
    ax1.set_ylabel('Number of Wins', fontsize=14)
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add count and percentage labels
    for i, (count, percentage) in enumerate(zip(win_counts, percentages)):
        ax1.text(i, count + 0.3, f"{count} ({percentage}%)", 
                ha='center', fontsize=12, fontweight='bold')
    
    ax1.set_ylim(0, max(win_counts) * 1.2)
    
    # 2. Average category scores (top right)
    # Initialize score dictionaries based on detected fields
    model1_scores = {field: [] for field in detected_fields}
    model2_scores = {field: [] for field in detected_fields}
    
    # Extract scores from JSON feedback
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                for field in detected_fields:
                    if field in data["model1_score"]:
                        model1_scores[field].append(data["model1_score"][field])
                    
                    if field in data["model2_score"]:
                        model2_scores[field].append(data["model2_score"][field])
            except:
                continue
    
    # Calculate averages
    model1_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model1_scores.items()}
    model2_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model2_scores.items()}
    
    # Get category display names
    if LEVEL in CATEGORY_FIELDS:
        category_display = [CATEGORY_FIELDS[LEVEL].get(field, field.replace('_', ' ').title()) 
                           for field in detected_fields]
    else:
        category_display = [field.replace('_', ' ').title() for field in detected_fields]
    
    ax2 = fig.add_subplot(gs[0, 1])
    
    # Set positions for bars
    pos = list(range(len(category_display)))
    width = 0.35
    
    # Create bars
    ax2.bar([p - width/2 for p in pos], list(model1_avgs.values()), width, 
            alpha=0.8, color='#4CAF50', label='Your Chatbot')
    
    ax2.bar([p + width/2 for p in pos], list(model2_avgs.values()), width, 
            alpha=0.8, color='#2196F3', label='GPT-4o-mini')
    
    # Set axes and labels
    ax2.axhline(y=3, linestyle='--', color='gray', alpha=0.5)
    ax2.set_ylabel('Average Score (0-5)', fontsize=14)
    ax2.set_title('Average Category Scores', fontsize=16)
    ax2.set_xticks(pos)
    ax2.set_xticklabels(category_display, fontsize=11, rotation=30, ha='right')
    ax2.set_yticks(range(6))
    ax2.grid(axis='y', linestyle='--', alpha=0.3)
    
    # Add value labels
    for i, v in enumerate(model1_avgs.values()):
        ax2.text(i - width/2, v + 0.1, f"{v:.1f}", ha='center', fontsize=10)
    
    for i, v in enumerate(model2_avgs.values()):
        ax2.text(i + width/2, v + 0.1, f"{v:.1f}", ha='center', fontsize=10)
    
    ax2.legend(fontsize=12)
    ax2.set_ylim(0, 5.5)
    
    # 3. Score distribution (middle)
    # Extract total scores
    model1_totals = []
    model2_totals = []
    
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                if "total" in data["model1_score"]:
                    model1_totals.append(data["model1_score"]["total"])
                
                if "total" in data["model2_score"]:
                    model2_totals.append(data["model2_score"]["total"])
            except:
                continue
    
    # Create DataFrame
    scores_df = pd.DataFrame({
        'Your Chatbot': model1_totals,
        'GPT-4o-mini': model2_totals
    })
    
    ax3 = fig.add_subplot(gs[1, :])
    
    # Boxplot
    sns.boxplot(data=scores_df, ax=ax3, palette=['#4CAF50', '#2196F3'])
    
    # Add strip plot for individual points
    sns.stripplot(data=scores_df, ax=ax3, color='black', alpha=0.5, jitter=True)
    
    # Add mean values
    for i, col in enumerate(scores_df.columns):
        mean_val = scores_df[col].mean()
        ax3.text(i, scores_df[col].max() + 0.5, f'Mean: {mean_val:.1f}', 
                 ha='center', fontsize=11, fontweight='bold')
    
    ax3.set_title('Distribution of Total Scores (Out of 25)', fontsize=16)
    ax3.set_ylabel('Total Score', fontsize=14)
    ax3.grid(axis='y', linestyle='--', alpha=0.3)
    ax3.set_ylim(0, 25.5)
    
    # Adding title to the figure
    fig.suptitle(f'DSA Chatbot Evaluation Results for {LEVEL.capitalize()} Users', fontsize=20, y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(f'evaluation_results/{LEVEL}/evaluation_dashboard.png', dpi=300, bbox_inches='tight')
    plt.close()

# Run all visualizations
def visualize_all_results():
    try:
        print("Generating win comparison chart...")
        win_counts, percentages = plot_win_comparison()
        
        print("Generating category scores visualization...")
        category_results = plot_category_scores()
        
        print("Generating score distribution boxplot...")
        score_distribution = plot_score_distribution()
        
        
        print("Creating comprehensive dashboard...")
        create_evaluation_dashboard()
        
        print(f"All visualizations completed and saved to 'evaluation_results/{LEVEL}' directory")
        return True
    except Exception as e:
        print(f"Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()
        return False

# Generate all visualizations
if __name__ == "__main__":
    print(f"Running visualization for {LEVEL.capitalize()} level")
    visualize_all_results()