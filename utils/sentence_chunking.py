import os
import nltk
from transformers import AutoTokenizer

def ensure_nltk_data(package_name, nltk_data_path):
    if package_name == "punkt" or package_name == "punkt_tab":
        package_dir = os.path.join(nltk_data_path, "tokenizers", package_name)
        zip_file = os.path.join(package_dir, "tokenizers",f"{package_name}.zip")
    else:
        package_dir = os.path.join(nltk_data_path, package_name)
        zip_file = os.path.join(package_dir, f"{package_name}.zip")
        
    print(f"Checking for {package_name} data in {package_dir}")
    if os.path.exists(package_dir) or os.path.exists(zip_file):
        print(f"{package_name} data found in {package_dir}")
    else:
        print(f"{package_name} data not found in {package_dir}")
        print(f"Downloading {package_name} data")
        nltk.download(package_name, download_dir=nltk_data_path)
        if os.path.exists(package_dir) or os.path.exists(zip_file):
            print(f"{package_name} data downloaded successfully")
        else:
            print(f"Error downloading {package_name} data")
            
# Get the NLTK data path
nltk_data_path = nltk.data.path[0]

# Ensure the NLTK data is downloaded
ensure_nltk_data("punkt", nltk_data_path)
ensure_nltk_data("punkt_tab", nltk_data_path)

def get_sentence_chunks(text, tokenizer, min_chunk_size=150, max_chunk_size=250, overlap_size=50):
    try:
        # Tokenize the text into sentences
        sentences = nltk.sent_tokenize(text)

        # Initialize variables
        chunks = []  # List to hold all chunks
        current_chunk_tokens = []  # Current chunk tokens
        current_chunk_length = 0  # Current chunk length

        # Process each sentence
        for sentence in sentences:
            # Tokenize the sentence into subword tokens
            sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False, truncation=False)
            sentence_length = len(sentence_tokens)

            # If the sentence is longer than max_chunk_size, split it
            if sentence_length > max_chunk_size:
                for i in range(0, sentence_length, max_chunk_size):
                    chunk_tokens = sentence_tokens[i:i + max_chunk_size]
                    chunks.append(tokenizer.decode(chunk_tokens))
                continue  # Move to next sentence after handling long sentence

            # Check if the current chunk will exceed max_chunk_size
            if current_chunk_length + sentence_length > max_chunk_size:
                # Add the current chunk to the list
                chunks.append(tokenizer.decode(current_chunk_tokens))

                # Start a new chunk with overlap if necessary
                current_chunk_tokens = current_chunk_tokens[-overlap_size:] if overlap_size > 0 else []
                current_chunk_length = len(current_chunk_tokens)

            # Add sentence tokens to the current chunk
            current_chunk_tokens.extend(sentence_tokens)
            current_chunk_length += sentence_length

        # Add any remaining tokens as the last chunk
        if current_chunk_tokens and current_chunk_length >= min_chunk_size:
            chunks.append(tokenizer.decode(current_chunk_tokens))

        return chunks

    except Exception as e:
        print(f"An error occurred: {e}")
        return []




