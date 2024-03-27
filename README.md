# AICL
The code implementation for "Adaptive In-Context Learning with Large Language Models for Bundle Generation"

### Overview:
This project contains the code implementation for the experiments presented in the paper titled "Adaptive In-Context Learning with Large Language Models for Bundle Generation". The purpose of this code is to reproduce the experiments and results mentioned in the paper. Users are required to replace the OpenAI API key with their own key to execute the code successfully.


### Requirements:
- Python (version >= 3.8)
- OpenAI/Claude API key 

### Getting Started

1. Download this project to your local machine.

2. Navigate to the project directory:
```
cd AICL
```

3. Install the required Python packages:
```
pip install -r requirements.txt
```

### Configuration

Open the `config.yaml` file and replace the placeholder for the OpenAI/Claude API key with your own key:
```
api_key: 'your_own_key_here'
```


### Running the Code

Execute the following command to run the experiment script. Replace --dataset with the desired dataset name (e.g., 'electronic'):

```
python run.py --dataset electronic
```
This command will initiate the experiment, and the results for each step will be saved in the `temp/` folder.


### License

This project is licensed under the MIT License - see the LICENSE file for details.


