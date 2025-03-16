import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import json
from matplotlib.gridspec import GridSpec

# Load the graded results
df = pd.read_csv('graded_evaluation_results_cleaned.csv')

# Create a directory for the visualizations
import os
os.makedirs('evaluation_plots/intermediate', exist_ok=True)

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
    
    plt.title('Overall Performance Comparison', fontsize=16, pad=20)
    plt.ylabel('Number of Wins', fontsize=14)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add count and percentage labels on bars
    for i, (count, percentage) in enumerate(zip(win_counts, percentages)):
        ax.text(i, count + 0.3, f"{count} ({percentage}%)", 
                ha='center', fontsize=12, fontweight='bold')
    
    plt.ylim(0, max(win_counts) * 1.2)  # Add space for labels
    plt.tight_layout()
    plt.savefig('evaluation_plots/win_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return win_counts, percentages

# 2. Score Breakdown by Category
def plot_category_scores():
    # Extract scores from JSON feedback
    model1_scores = {
        "technical_accuracy": [],
        "beginner_accessibility": [],
        "clarity_examples": [],
        "educational_value": [],
        "practical_application": []
    }
    
    model2_scores = {
        "technical_accuracy": [],
        "beginner_accessibility": [],
        "clarity_examples": [],
        "educational_value": [],
        "practical_application": []
    }
    
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                for category in model1_scores:
                    if category in data["model1_score"]:
                        model1_scores[category].append(data["model1_score"][category])
                    
                    if category in data["model2_score"]:
                        model2_scores[category].append(data["model2_score"][category])
            except:
                continue
    
    # Calculate averages for each category
    model1_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model1_scores.items()}
    model2_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model2_scores.items()}
    
    # Make results dataframe
    results_df = pd.DataFrame({
        'Category': [cat.replace('_', ' ').title() for cat in model1_scores.keys()],
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
    
    plt.title('Average Scores by Category for Beginner Users', fontsize=16, y=1.08)
    plt.tight_layout()
    plt.savefig('evaluation_plots/category_radar.png', dpi=300, bbox_inches='tight')
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
    plt.title('Average Category Scores for Beginner Users', fontsize=16, pad=20)
    plt.xticks(pos, categories, fontsize=12, rotation=30, ha='right')
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
    plt.savefig('evaluation_plots/category_bars.png', dpi=300, bbox_inches='tight')
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
    
    plt.title('Distribution of Total Scores (Out of 25)', fontsize=16, pad=20)
    plt.ylabel('Total Score', fontsize=14)
    plt.grid(axis='y', linestyle='--', alpha=0.3)
    plt.ylim(0, 25.5)  # Set y-axis limit to maximum possible score
    plt.tight_layout()
    plt.savefig('evaluation_plots/score_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return scores_df

# 4. Score Difference Analysis
def plot_score_differences():
    differences = []
    questions = []
    winners = []
    
    for i, feedback in enumerate(df['grading_feedback']):
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                model1_total = data["model1_score"]["total"]
                model2_total = data["model2_score"]["total"]
                
                diff = model1_total - model2_total
                differences.append(diff)
                
                # Get original question (shortened)
                question = df.iloc[i]['question']
                if len(question) > 50:
                    question = question[:47] + "..."
                questions.append(question)
                
                # Get winner
                winners.append(data['winner'])
                
            except:
                continue
    
    # Create DataFrame for differences
    diff_df = pd.DataFrame({
        'Question': questions,
        'Difference': differences,
        'Winner': winners
    })
    
    # Sort by difference
    diff_df = diff_df.sort_values('Difference')
    
    # Plot the differences
    plt.figure(figsize=(12, len(diff_df) * 0.4 + 2))
    
    # Set colors based on winner
    colors = ['#4CAF50' if d > 0 else '#2196F3' if d < 0 else '#9E9E9E' for d in diff_df['Difference']]
    
    # Create horizontal bar chart
    bars = plt.barh(range(len(diff_df)), diff_df['Difference'], color=colors)
    
    # Add vertical line at 0
    plt.axvline(x=0, color='black', linestyle='-', alpha=0.7)
    
    # Add labels
    plt.xlabel('Score Difference (Your Chatbot - GPT-4o-mini)', fontsize=14)
    plt.yticks(range(len(diff_df)), diff_df['Question'], fontsize=9)
    plt.title('Score Differences by Question', fontsize=16, pad=20)
    
    # Add grid lines
    plt.grid(axis='x', linestyle='--', alpha=0.3)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#4CAF50', label='Your Chatbot Better'),
        Patch(facecolor='#2196F3', label='GPT-4o-mini Better'),
        Patch(facecolor='#9E9E9E', label='Tie')
    ]
    plt.legend(handles=legend_elements, loc='lower right')
    
    plt.tight_layout()
    plt.savefig('evaluation_plots/score_differences.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return diff_df

# 5. Create a comprehensive dashboard
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
    # Extract scores from JSON feedback
    model1_scores = {
        "technical_accuracy": [],
        "beginner_accessibility": [],
        "clarity_examples": [],
        "educational_value": [],
        "practical_application": []
    }
    
    model2_scores = {
        "technical_accuracy": [],
        "beginner_accessibility": [],
        "clarity_examples": [],
        "educational_value": [],
        "practical_application": []
    }
    
    for feedback in df['grading_feedback']:
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                
                for category in model1_scores:
                    if category in data["model1_score"]:
                        model1_scores[category].append(data["model1_score"][category])
                    
                    if category in data["model2_score"]:
                        model2_scores[category].append(data["model2_score"][category])
            except:
                continue
    
    # Calculate averages
    model1_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model1_scores.items()}
    model2_avgs = {cat: sum(scores)/len(scores) if scores else 0 for cat, scores in model2_scores.items()}
    
    # Create DataFrame
    categories = [cat.replace('_', ' ').title() for cat in model1_scores.keys()]
    
    ax2 = fig.add_subplot(gs[0, 1])
    
    # Set positions for bars
    pos = list(range(len(categories)))
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
    ax2.set_xticklabels(categories, fontsize=12, rotation=30, ha='right')
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
    
    # 4. Difference analysis (bottom)
    differences = []
    questions = []
    winners = []
    
    # Only take the top 15 most significant differences to maintain readability
    valid_entries = []
    
    for i, feedback in enumerate(df['grading_feedback']):
        if pd.notna(feedback) and not feedback.startswith(('Skipped', 'JSON', 'Grading')):
            try:
                data = json.loads(feedback)
                model1_total = data["model1_score"]["total"]
                model2_total = data["model2_score"]["total"]
                diff = model1_total - model2_total
                
                valid_entries.append((i, abs(diff), diff))
            except:
                continue
    
    # Sort by absolute difference
    valid_entries.sort(key=lambda x: x[1], reverse=True)
    
    # Take top 15
    top_entries = valid_entries[:15]
    
    for i, _, diff in top_entries:
        feedback = df['grading_feedback'].iloc[i]
        
        try:
            data = json.loads(feedback)
            
            # Get original question (shortened)
            question = df.iloc[i]['question']
            if len(question) > 40:
                question = question[:37] + "..."
            
            questions.append(question)
            differences.append(diff)
            winners.append(data['winner'])
            
        except:
            continue
    
    # Sort for visualization
    indices = np.argsort(differences)
    sorted_differences = [differences[i] for i in indices]
    sorted_questions = [questions[i] for i in indices]
    
    ax4 = fig.add_subplot(gs[2, :])
    
    # Set colors
    colors = ['#4CAF50' if d > 0 else '#2196F3' if d < 0 else '#9E9E9E' for d in sorted_differences]
    
    # Create horizontal bar chart
    ax4.barh(range(len(sorted_differences)), sorted_differences, color=colors)
    
    # Add vertical line
    ax4.axvline(x=0, color='black', linestyle='-', alpha=0.7)
    
    # Add labels
    ax4.set_xlabel('Score Difference (Your Chatbot - GPT-4o-mini)', fontsize=14)
    ax4.set_yticks(range(len(sorted_questions)))
    ax4.set_yticklabels(sorted_questions, fontsize=10)
    ax4.set_title('Most Significant Score Differences by Question', fontsize=16)
    
    # Add grid
    ax4.grid(axis='x', linestyle='--', alpha=0.3)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#4CAF50', label='Your Chatbot Better'),
        Patch(facecolor='#2196F3', label='GPT-4o-mini Better'),
        Patch(facecolor='#9E9E9E', label='Tie')
    ]
    ax4.legend(handles=legend_elements, loc='lower right')
    
    # Adding title to the figure
    fig.suptitle('DSA Chatbot Evaluation Results for Beginner Users', fontsize=20, y=0.98)
    
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig('evaluation_plots/evaluation_dashboard.png', dpi=300, bbox_inches='tight')
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
        
        print("Generating score differences chart...")
        difference_analysis = plot_score_differences()
        
        print("Creating comprehensive dashboard...")
        create_evaluation_dashboard()
        
        print("All visualizations completed and saved to 'evaluation_plots' directory")
        return True
    except Exception as e:
        print(f"Error generating visualizations: {e}")
        return False

# Generate all visualizations
visualize_all_results()