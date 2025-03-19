
# Discord Bot Setup & Contribution Guide

## 🛠 Setup & Running the Discord Bot with Docker

### Prerequisites  
Ensure you have the following installed:  
- [Git](https://git-scm.com/downloads)  
- A [Discord bot token](https://discord.com/developers/applications)  
- [Docker](https://docs.docker.com/get-started/get-docker/)  
- [Docker Compose](https://docs.docker.com/compose/install/)

### 1️⃣ Clone the Repository  
```sh
git clone https://github.com/dillontherrien/arcanyx-log-bot.git
cd arcanyx-log-bot
```

### 2️⃣ Set Up Environment Variables  
Create a `.env` file in the root directory and add:  
```
BOT_TOKEN=your_discord_bot_token_here
MONGO_URL=your_mongodb_connection_string
```

### 3️⃣ Build & Start the Bot with Docker Compose  
```sh
docker-compose up --build -d
```

The `-d` flag runs the bot in detached mode (in the background).  
If you want to see logs, use:  
```sh
docker logs -f <container_name>
```

To stop the bot, run:  
```sh
docker-compose down
```

---

## 🤝 Contributing  

### Setting Up for Development (Without Docker)  
1. **Fork the Repository**  
2. **Clone Your Fork Locally**  
   ```sh
   git clone https://github.com/dillontherrien/arcanyx-log-bot.git
   cd arcanyx-log-bot
   ```
3. **Create a Feature Branch**  
   ```sh
   git checkout -b feature-branch-name
   ```
4. **Install Dependencies in a Virtual Environment** (For non-Docker development)  
   ```sh
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   venv\Scriptsctivate      # Windows
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
- Keep commit messages clear and descriptive.  
- Test changes before submitting a pull request.  
- When developing locally, consider using `docker-compose up --build` to test changes before committing.  
