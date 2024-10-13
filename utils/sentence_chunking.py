import os
import nltk
from transformers import AutoTokenizer

def ensure_nltk_data(package_name, nltk_data_path):
    if package_name == "punkt":
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

def get_sentence_chunks(text, tokenizer, min_chunk_size=150, max_chunk_size=250, chunk_overlap=True):
    try:
        # Tokenize the text into sentences
        sentences = nltk.sent_tokenize(text)
        
        # Initialize variables
        chunks = []  # List to hold all the chunks
        current_chunk = []  # Temporary storage for the current chunk
        current_length = 0  # Keeps track of the current chunk's length
        last_sentence = []  # Holds the tokens of the last sentence in the chunk, if overlap is enabled
        
        # Process each sentence
        for sentence in sentences:
            # Tokenize the sentence
            sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False)
            sentence_length = len(sentence_tokens)
            
            # Handle the case where the sentence is longer than the max_chunk_size
            if sentence_length > max_chunk_size:
                # Split the sentence into multiple chunks
                for i in range(0, sentence_length, max_chunk_size):
                    chunk = sentence_tokens[i:i+max_chunk_size]
                    chunks.append(tokenizer.decode(chunk))
            else:
                # Check if adding the sentence to the current chunk will exceed max_chunk_size
                if current_length + sentence_length > max_chunk_size:
                    # If chunk overlap is enabled, keep the last sentence of the current chunk
                    if chunk_overlap and last_sentence:
                        current_chunk.extend(last_sentence)
                        current_length += len(last_sentence)
                    
                    # Append the current chunk to the chunks list
                    chunks.append(tokenizer.decode(current_chunk))
                    
                    # Start a new chunk with the current sentence
                    current_chunk = sentence_tokens
                    current_length = sentence_length
                else:
                    # Add the sentence to the current chunk
                    current_chunk.extend(sentence_tokens)
                    current_length += sentence_length
            
            # Store the last sentence for overlapping
            last_sentence = sentence_tokens
        
        # Append any remaining chunk that was not added
        if current_chunk:
            chunks.append(tokenizer.decode(current_chunk))
        
        return chunks
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

# Example usage
if __name__ == "__main__":
    text = """
    The rapid advancement of technology in the 21st century has revolutionized various aspects of human life. 
    From the way we communicate to the way we work, technological innovations have reshaped society at an unprecedented pace. 
    At the heart of these changes is the internet, a global network that has transformed the flow of information, enabling instant communication and access to vast amounts of data. 
    Social media platforms, e-commerce websites, and digital services have proliferated, connecting billions of people and businesses across the globe. 
    This interconnectedness has not only fostered the exchange of ideas but has also facilitated the growth of the global economy.
    One of the most significant impacts of the internet is the democratization of knowledge. 
    In the past, access to information was often limited to those who had the means to obtain books, attend universities, or visit libraries. 
    Today, with just a few clicks, individuals can access educational resources, research papers, tutorials, and more, regardless of their geographical location or financial situation. 
    Massive Open Online Courses (MOOCs) and platforms like YouTube have made learning more accessible to millions of people. This shift has empowered individuals to acquire new skills and knowledge independently, fostering a culture of lifelong learning.
    However, this rapid technological progress has not been without its challenges. The rise of social media, for instance, has led to significant changes in the way people interact. 
    While these platforms have connected people across vast distances, they have also given rise to concerns about privacy, data security, and the spread of misinformation. Social media algorithms, designed to maximize user engagement, often promote sensational or controversial content, leading to echo chambers where users are exposed only to information that aligns with their existing beliefs. 
    This has contributed to the polarization of public discourse and the spread of false information, which can have real-world consequences, from influencing elections to inciting violence.
    In addition to these social challenges, the digital divide remains a significant issue. While billions of people now have access to the internet, there are still large populations, particularly in developing countries, who remain disconnected. 
    Lack of infrastructure, affordability, and digital literacy are some of the key barriers preventing widespread internet access. As the world becomes increasingly reliant on digital technologies, addressing this divide is crucial to ensuring that everyone can participate in the global economy and benefit from the opportunities that the internet provides.
    Artificial Intelligence (AI) is another technological advancement that is poised to have a profound impact on society. AI has the potential to revolutionize industries such as healthcare, education, and transportation by automating tasks, improving efficiency, and enabling the development of new products and services. 
    For example, in healthcare, AI-powered tools can assist doctors in diagnosing diseases, analyzing medical images, and personalizing treatment plans for patients. In education, AI can be used to create personalized learning experiences, helping students to learn at their own pace and according to their individual needs.
    Despite its potential benefits, the rise of AI also raises ethical concerns. As AI systems become more sophisticated, questions about bias, accountability, and job displacement have come to the forefront. 
    AI algorithms are often trained on vast amounts of data, and if this data is biased, the resulting AI systems can perpetuate and even amplify those biases. This can have serious implications, particularly in areas such as hiring, criminal justice, and lending, where biased decisions can lead to unfair treatment of individuals or groups. 
    Additionally, the automation of tasks previously performed by humans raises concerns about job displacement, as machines increasingly take over roles in industries such as manufacturing, transportation, and even white-collar jobs like accounting and legal services.
    """
    # Initialize a tokenizer from transformers (you can replace this with the tokenizer you use)
    tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
    
    # Call the function to get sentence chunks
    chunks = get_sentence_chunks(text, tokenizer, min_chunk_size=50, max_chunk_size=100, chunk_overlap=True)
    
    # Output the chunks
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i}: {chunk}")
