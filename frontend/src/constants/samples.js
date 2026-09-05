export const CODE_SAMPLES = [
  {
    id: 'py-sql-leak',
    label: 'Python: SQL Injection & Resource Leak',
    language: 'python',
    filename: 'user_repository.py',
    description: 'Contains string-formatted SQL queries and unclosed database cursor.',
    code: `import sqlite3

def get_user_by_username(username: str):
    # Bug: SQL Injection vulnerability via format string
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    query = f"SELECT id, username, email, is_admin FROM users WHERE username = '{username}'"
    cursor.execute(query)
    user = cursor.fetchone()
    
    # Bug: Missing cursor.close() and conn.close() resource leak
    return user

def process_batch(items=[]):
    # Bug: Mutable default argument retains state across calls
    items.append("processed")
    return items
`
  },
  {
    id: 'py-div-zero',
    label: 'Python: ZeroDivision & Range Off-by-One',
    language: 'python',
    filename: 'analytics.py',
    description: 'Contains unhandled zero division and index out of bounds error.',
    code: `def calculate_average_metrics(numbers):
    total = sum(numbers)
    # Bug: ZeroDivisionError when numbers list is empty
    avg = total / len(numbers)
    
    results = []
    # Bug: Off-by-one index out of bounds
    for i in range(len(numbers) + 1):
        diff = numbers[i] - avg
        results.append(diff)
        
    return avg, results
`
  },
  {
    id: 'js-xss-eval',
    label: 'JavaScript: XSS & Insecure Eval',
    language: 'javascript',
    filename: 'renderer.js',
    description: 'Contains innerHTML injection and dangerous eval usage.',
    code: `function renderUserProfile(userData) {
    // Security Bug: Dangerous eval on untrusted data
    const parsedData = eval("(" + userData.rawConfig + ")");
    
    const container = document.getElementById("profile-card");
    // Security Bug: Direct innerHTML injection allows stored XSS
    container.innerHTML = "<h3>" + userData.name + "</h3><p>" + userData.bio + "</p>";
    
    // Style Bug: Loose equality
    if (userData.role == "admin") {
        container.style.borderColor = "red";
    }
}
`
  },
  {
    id: 'js-mem-leak',
    label: 'JavaScript: Memory Leak & Race Condition',
    language: 'javascript',
    filename: 'dataWatcher.js',
    description: 'Contains unremoved event listeners and unhandled promise rejection.',
    code: `class DataWatcher {
    constructor(emitter) {
        this.emitter = emitter;
        this.cache = [];
        // Bug: Event listener added without cleanup causes memory leak
        this.emitter.on("data", (chunk) => {
            this.cache.push(chunk);
        });
    }

    async fetchData(url) {
        // Bug: Missing try/catch or error handler on async fetch
        const response = await fetch(url);
        const data = await response.json();
        return data;
    }
}
`
  }
];
