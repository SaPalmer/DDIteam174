# cse6242-project-team174

## Description
This package provides tools for downloading, preprocessing, and visualizing drug-drug interaction data. The application includes scripts to fetch data from the FDA API, preprocess it, and generate interactive visualizations. Additionally,  it integrates with OpenAI for enhanced data analysis and insights.

## Installation
1. **Clone the repository:**
    ```bash
    git clone https://github.gatech.edu/kschnieders3/cse6242-project-team174
    cd cse6242-project-team174
    ```

2. **Set up a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Configure Environment Variables:**
    - Create a `.env` file in the root directory of the project.
    - Add the following variables to the `.env` file:
        - The integration with OpenAI enables local users to get simplified summaries of medication side effects as well as a typical severity to minimize potential confusion from medical jargon.

        ```properties
        OPEN_AI_SECRET_KEY=your_openai_api_key_here
        INGESTION_MODEL=gpt-4o-mini
        ```

    - **Setting Up OpenAI API Key:**
        - **Sign Up / Log In:**  
          Visit [OpenAI](https://platform.openai.com/) and sign up for an account or log in if you already have one.
        - **Generate API Key:**  
          Navigate to the API section in your OpenAI dashboard and generate a new API key.
        - **Update `.env` File:**  
          Replace `your_openai_api_key_here` with the API key you obtained from OpenAI.

        **Example:**
        ```properties
        OPEN_AI_SECRET_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        INGESTION_MODEL=gpt-4o-mini
        ```

## Setting Up the Dataset
The repo ships with a sample dataset (~200mb) for testing. This dataset can be opened up by running the preprocessing script below.

Run the setup script to download and preprocess the data. The --max_files flag sets the maximum number of FDA JSON files to process (few files = smaller dataset to test with).

```bash
python setup_dataset.py --max_files=10
```

## Starting the Viz
Run the app.py file! This is the main file to start the data viz. This will spin up a local server to run the dash application in-browser.

```bash
python app.py
```
