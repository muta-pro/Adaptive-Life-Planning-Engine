#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <cstdlib>
#include <iomanip>
#include <ctime> // Added for time tracking

// ANSI escape codes for an elegant, colorful terminal UI
#define RESET       "\033[0m"
#define BOLD        "\033[1m"
#define TEAL        "\033[38;5;51m"
#define INDIGO      "\033[38;5;63m"
#define RED         "\033[38;5;196m"
#define GREEN       "\033[38;5;46m"
#define SLATE       "\033[38;5;244m"

using namespace std;

// Represents a single action in your flow state
enum TaskStatus { PENDING, DONE, BLACKHOLE };

struct Task {
    int id;
    string name;
    string discipline;
    TaskStatus status;

    Task(int id, string n, string d) : id(id), name(n), discipline(d), status(PENDING) {}
};

// The core engine that manages vectors (C++ containers) and logic
class SkrovEngine {
private:
    vector<Task> queue;
    int nextId;
    int flowScore;
    int blackholeCount;

public:
    SkrovEngine() : nextId(1), flowScore(0), blackholeCount(0) {}

    void addTask(const string& name, const string& discipline) {
        queue.push_back(Task(nextId++, name, discipline));
        cout << TEAL << "  [+] Task added to queue: " << name << RESET << "\n";
    }

    void listTasks() {
        cout << "\n" << INDIGO << BOLD << "  === SKROV DAILY QUEUE ===" << RESET << "\n";
        bool hasPending = false;
        
        // Iterating through our standard vector
        for (size_t i = 0; i < queue.size(); ++i) {
            if (queue[i].status == PENDING) {
                hasPending = true;
                cout << "  [" << queue[i].id << "] " 
                     << left << setw(25) << queue[i].name 
                     << SLATE << " (" << queue[i].discipline << ")" << RESET << "\n";
            }
        }
        if (!hasPending) cout << SLATE << "  No pending tasks in the queue. You are free." << RESET << "\n";
        cout << "\n";
    }

    void enterDeepFocus() {
        Task* current = NULL;
        for (size_t i = 0; i < queue.size(); ++i) {
            if (queue[i].status == PENDING) {
                current = &queue[i];
                break;
            }
        }

        if (!current) {
            cout << GREEN << "  Queue empty. Flow state achieved. Go rest." << RESET << "\n";
            return;
        }

        // Clear screen for pure focus (works on Unix/Mac)
        system("clear");
        cout << "\n" << TEAL << BOLD << "  >>> DEEP FOCUS ENGAGED <<<" << RESET << "\n\n";
        cout << "  Current Target : " << BOLD << current->name << RESET << "\n";
        cout << "  Discipline     : " << SLATE << current->discipline << RESET << "\n\n";
        cout << "  Action required:\n";
        cout << "  Type 'done' to complete, or 'skip' to banish to the Blackhole.\n\n";
        cout << "  " << TEAL << "skrov-focus> " << RESET;

        string command;
        getline(cin, command);

        if (command == "done") {
            current->status = DONE;
            flowScore += 15;
            cout << GREEN << "  [✓] Task crushed. Score +15. Total Score: " << flowScore << RESET << "\n";
        } else if (command == "skip") {
            current->status = BLACKHOLE;
            blackholeCount++;
            flowScore = 0; // The Blackhole penalty
            cout << RED << "  [🕳️] Task consumed by the Blackhole. Score reset to 0." << RESET << "\n";
        } else {
            cout << SLATE << "  Focus broken. Returning to menu." << RESET << "\n";
        }
    }

    void displayDayProgress() {
        // Fetch current system time
        time_t now = time(0);
        tm *ltm = localtime(&now);

        // Calculate total seconds passed since midnight
        int secondsPassed = (ltm->tm_hour * 3600) + (ltm->tm_min * 60) + ltm->tm_sec;
        float percentage = (secondsPassed / 86400.0f) * 100.0f; // 86400 seconds in a day

        int barWidth = 30; // Length of the progress bar
        int filled = (percentage / 100.0f) * barWidth;

        cout << "\n" << SLATE << "  Time Burn: [";
        for (int i = 0; i < barWidth; ++i) {
            if (i < filled) {
                // Change color based on how much day is left (Green -> Teal -> Red)
                if (percentage > 85.0f) cout << RED << "■";
                else cout << TEAL << "■";
            } else {
                cout << SLATE << "-"; // Empty space
            }
        }
        cout << SLATE << "] " << fixed << setprecision(1) << percentage << "%" << RESET << "\n";
    }

    void displayStats() {
        displayDayProgress();
        cout << SLATE << "  Score: " << TEAL << flowScore 
             << SLATE << " | Blackholed Tasks: " << RED << blackholeCount << RESET << "\n";
    }
};

void printHelp() {
    cout << "\n" << SLATE << "  Commands:" << RESET << "\n";
    cout << "  " << TEAL << "add <name> | <discipline>" << SLATE << " - Add a new task" << RESET << "\n";
    cout << "  " << TEAL << "ls" << SLATE << "                        - List pending queue" << RESET << "\n";
    cout << "  " << TEAL << "focus" << SLATE << "                     - Enter Deep Focus for the next task" << RESET << "\n";
    cout << "  " << TEAL << "exit" << SLATE << "                      - Close SKROV" << RESET << "\n";
}

int main() {
    // Clear screen for clean startup
    system("clear");
    
    SkrovEngine engine;
    cout << TEAL << BOLD << "\n  S K R O V   A R C H I T E C T U R E\n" << RESET;
    cout << SLATE << "  Fast. Elegant. Unrelenting Focus.\n" << RESET;

    // Pre-load some tasks from your actual notes
    engine.addTask("module8>ex00", "L");
    engine.addTask("web serv", "L");
    engine.addTask("gym", "S");

    string input;
    while (true) {
        engine.displayStats();
        cout << "\n" << INDIGO << "skrov> " << RESET;
        
        if (!getline(cin, input)) break; // Handle Ctrl+D gracefully

        if (input == "exit" || input == "quit") {
            cout << TEAL << "  Exiting SKROV. Stay sharp." << RESET << "\n";
            break;
        } 
        else if (input == "ls") {
            engine.listTasks();
        } 
        else if (input == "focus") {
            engine.enterDeepFocus();
        } 
        else if (input.find("add ") == 0) {
            string data = input.substr(4);
            size_t delimPos = data.find("|");
            if (delimPos != string::npos) {
                // Parse strings based on delimiter
                string name = data.substr(0, delimPos);
                string disc = data.substr(delimPos + 1);
                
                // Trim trailing/leading spaces manually for C++98 compatibility
                name.erase(name.find_last_not_of(" \n\r\t")+1);
                disc.erase(0, disc.find_first_not_of(" \n\r\t"));
                
                engine.addTask(name, disc);
            } else {
                cout << RED << "  Invalid format. Use: add <name> | <discipline>" << RESET << "\n";
            }
        } 
        else if (input == "help") {
            printHelp();
        }
        else if (input != "") {
            cout << RED << "  Unknown command. Type 'help'." << RESET << "\n";
        }
    }
    return 0;
}