from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
import os
import subprocess
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import json

load_dotenv()

class CodeResponse(BaseModel):
    file_name: str
    code: str
    language: str

app = FastAPI()

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create directories for saved code
SCRIPTS_DIR = Path("generated_scripts")
SCRIPTS_DIR.mkdir(exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def get_file_extension(language: str) -> str:
    extensions = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "java": ".java",
        "csharp": ".cs",
        "cpp": ".cpp",
        "c": ".c",
        "go": ".go",
        "rust": ".rs",
        "ruby": ".rb",
        "php": ".php",
        "swift": ".swift",
        "kotlin": ".kt"
    }
    return extensions.get(language.lower(), ".txt")

@app.post("/generate")
async def generate_code(request: Request, question: str = Form(...)):
    try:
        # Call OpenAI API to generate code using the new client format
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a code generation assistant that MUST ALWAYS return a valid JSON string containing ONLY the following structure, with no additional text or explanation:
                {
                    "language": "programming_language_name",
                    "file_name": "descriptive_name_for_the_code",
                    "code": "the_actual_code_properly_indented"
                }
                
                Rules:
                1. language: Choose the most appropriate programming language
                2. file_name: Use descriptive names (e.g., binary_search_implementation, quick_sort_algorithm)
                3. code: Include properly indented, working code with no markdown formatting
                4. Format: Ensure the response is a valid, parseable JSON string
                5. Do not include ANY text outside the JSON structure
                6. The response must begin with { and end with }
                7. alway add standard documenation for the code like what this code does, what is the input and output of the code and also the prompt the user has given to generate this code in nice correct format
                """},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=8000
        )
        
        # Extract and parse the content
        content = response.choices[0].message.content
        response_data = json.loads(content)
        
        # Get proper file extension
        extension = get_file_extension(response_data["language"])
        # full_filename = f"{response_data['file_name']}{extension}"
        full_filename = f"{response_data['file_name']}{extension}"
        
        # Save the code to a file
        file_path = SCRIPTS_DIR / full_filename
        with open(file_path, "w") as f:
            f.write(response_data["code"])
        
        # Execute the code if it's Python
        execution_output = ""
        execution_error = ""
        if extension == ".py":
            try:
                result = subprocess.run(
                    ["python", str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                execution_output = result.stdout
                execution_error = result.stderr
            except subprocess.TimeoutExpired:
                execution_error = "Execution timed out after 10 seconds"
        else:
            execution_output = f"Execution not supported for {response_data['language']} files."
        
        return {
            "code": response_data["code"],
            "filename": full_filename,
            "language": response_data["language"],
            "output": execution_output,
            "error": execution_error
        }
        
    except json.JSONDecodeError:
        return {"error": "Failed to decode the JSON response from OpenAI. Please ensure the response format is correct."}
    except Exception as e:
        return {"error": str(e)}