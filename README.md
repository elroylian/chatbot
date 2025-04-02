# DSA Chatbot with Retrieval Augmented Generation

A conversational assistant for learning Data Structures and Algorithms that adapts to your level of understanding.

![Version](https://img.shields.io/badge/version-2.3.0-blue)

## 🌟 Features

- **Adaptive Learning Experience**: Automatically assesses and adjusts to your knowledge level (beginner, intermediate, advanced)
- **Context-Aware Explanations**: Provides personalized explanations based on your competency level
- **Document Analysis**: Upload images and PDFs with DSA content for analysis and explanation
- **Learning Journey Tracking**: Monitors your progress and recommends new topics to explore
- **Retrieval-Augmented Generation**: Uses vector search to provide accurate and relevant DSA information

## 📋 System Architecture

The DSA Chatbot is built with a modular architecture focused on delivering personalized learning experiences:

- **LLM Integration**: Powered by state-of-the-art language models
- **Vector Database**: Enables semantic search for accurate information retrieval
- **Document Processing Pipeline**: Supports analysis of uploaded educational materials
- **User Assessment Framework**: Evaluates and tracks learning progress
- **Streamlit Interface**: Provides an accessible user experience

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- OpenAI API key
- Zilliz Cloud account (or other vector database)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/elroylian/dsa-chatbot.git
cd dsa-chatbot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `secrets.toml` file in the `.streamlit` directory with your credentials:
```toml
OpenAI_key = "your-openai-api-key"
ZILLIZ_CLOUD_URI = "your-zilliz-endpoint"
ZILLIZ_CLOUD_USERNAME = "your-zilliz-username"
ZILLIZ_CLOUD_PASSWORD = "your-zilliz-password"
ZILLIZ_CLOUD_API_KEY = "your-zilliz-api-key"
```

4. Run the application:
```bash
streamlit run streamlit_app.py
```

## 🧠 Using the Chatbot

1. **Register/Login**: Create an account to track your learning progress
2. **Initial Assessment**: The system will assess your DSA knowledge level
3. **Ask Questions**: Interact with the chatbot about any DSA topic
4. **Upload Documents**: Share DSA-related images or PDFs for explanation
5. **Track Progress**: View your learning journey and get topic recommendations

## 🔧 System Capabilities

### Knowledge Assessment
The chatbot evaluates your understanding across three levels:
- **Beginner**: Focuses on fundamentals with clear examples
- **Intermediate**: Balances theory with practical implementation details
- **Advanced**: Provides in-depth analysis and optimization insights

### Document Processing
Upload and analyze:
- Images containing DSA concepts, diagrams, or code
- PDF documents with algorithm explanations or technical content

### Learning Journey
- Track topics you've covered
- Receive personalized recommendations for what to learn next
- Visualize your knowledge progression

## 🛠️ Technical Implementation

Built with:
- **Python** - Core programming language
- **Streamlit** - Web interface framework
- **LangChain/LangGraph** - LLM orchestration and workflows
- **OpenAI API** - Language model integration
- **Zilliz Cloud** - Vector database for semantic search
- **SQLite** - Local database for user information and history

## 🔍 Project Structure

```
.
├── utils/                  # Utility modules
│   ├── analyser.py         # User level assessment
│   ├── chunk_doc.py        # Document chunking and retrieval
│   ├── db_connection.py    # Database operations
│   ├── level_manager.py    # User level management
│   ├── model.py            # LLM configuration
│   └── topic_recommendation.py  # Learning recommendations
├── templates/         # Workflow definitions
│   ├── document_text_template.py  # Document processing
│   ├── intial_template.py  # Initial assessment
│   ├── memory.py           # State management
│   └── text_template.py    # Text processing workflow
├── streamlit_app.py        # Main application entry point
├── requirements.txt        # Dependencies
└── config.yaml             # Authentication configuration
```

## 📚 Educational Focus

The DSA Chatbot is designed to help students learn complex DSA concepts by:
- Providing explanations appropriate to their knowledge level
- Visualizing and explaining algorithms and data structures
- Connecting theoretical concepts to practical implementations
- Offering personalized guidance through learning paths

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contact

For questions or feedback, please open an issue on GitHub.