# Discord Bot Setup & Contribution Guide

## 🛠 Setup & Running the Discord Bot

### Prerequisites  
Ensure you have the following installed:  
- [Python 3.9+](https://www.python.org/downloads/)  
- [pip](https://pip.pypa.io/en/stable/installation/)  
- [Git](https://git-scm.com/downloads)  
- A [Discord bot token](https://discord.com/developers/applications)
- [Docker](https://docs.docker.com/get-started/get-docker/)

### 1️⃣ Clone the Repository  
```sh
git clone https://github.com/dillontherrien/arcanyx-log-bot.git
cd your-repo-name
```

### 2️⃣ Create a Virtual Environment  
```sh
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate      # Windows
```

### 3️⃣ Install Dependencies  
```sh
pip install -r requirements.txt
```

### 4️⃣ Set Up Environment Variables  
Create a `.env` file in the root directory and add:  
```
BOT_TOKEN=your_discord_bot_token_here
```

### 5️⃣ Run the Bot  
```sh
python main.py
```

---

## 🤝 Contributing  

### Setting Up for Development  
1. **Fork the Repository**  
2. **Clone Your Fork Locally**  
   ```sh
   git clone https://github.com/dillontherrien/arcanyx-log-bot.git
   cd your-repo-name
   ```
3. **Create a Feature Branch**  
   ```sh
   git checkout -b feature-branch-name
   ```
4. **Install Dependencies in a Virtual Environment**  
   ```sh
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```
5. **Make Your Changes & Commit**  
   ```sh
   git add .
   git commit -m "Describe your changes"
   ```
6. **Push & Create a Pull Request**  
   ```sh
   git push origin feature-branch-name
   ```
   Then, go to the GitHub repository and create a pull request.

### Code Style & Best Practices  
- Follow **PEP8** for Python coding style.  
- Keep commit messages clear and descriptive.  
- Test changes before submitting a pull request.  
