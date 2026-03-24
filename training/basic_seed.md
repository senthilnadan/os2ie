Single transition — one tool, one output into state

  ┌─────┬────────────────────────────────────────────┬──────────────────────────┬────────────────────────────┐
  │  #  │                    Task                    │           Tool           │        State needed        │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 1   │ Check whether hello.py exists              │ exists                   │ file_path                  │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 2   │ List all files in the project folder       │ list_directory_recursive │ directory_path             │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 3   │ Read the contents of README.md             │ read_file                │ file_path                  │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 4   │ Delete temp.txt                            │ delete_file              │ file_path                  │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 5   │ Create notes.txt with content "first note" │ create_file              │ file_path, content         │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 6   │ Check Python version                       │ run_shell_command        │ command, working_directory │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 7   │ Count all Python files in the project      │ run_shell_command        │ command, working_directory │
  ├─────┼────────────────────────────────────────────┼──────────────────────────┼────────────────────────────┤
  │ 8   │ Find all files containing "import fastapi" │ run_shell_command        │ command, working_directory │
  └─────┴────────────────────────────────────────────┴──────────────────────────┴────────────────────────────┘

  ---
  Multi-step — state threads between transitions

  ┌─────┬───────────────────────────────────────────┬───────────────────────────────┬────────────────────────────┐
  │  #  │                   Task                    │             Tools             │       What it tests        │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
  │ 9   │ Create temp.txt with "hello" then read it │ create_file → read_file       │ output of t1 feeds t2      │
  │     │  back                                     │                               │                            │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
  │ 10  │ Create log.txt, append "line1", append    │ create_file → append_to_file  │ file_path reused across    │
  │     │ "line2"                                   │ × 2                           │ steps                      │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
  │ 11  │ Create a folder, then create a file       │ make_directory → create_file  │ directory_path feeds       │
  │     │ inside it                                 │                               │ file_path                  │
  ├─────┼───────────────────────────────────────────┼───────────────────────────────┼────────────────────────────┤
  │ 12  │ Run a shell command and write its stdout  │ run_shell_command →           │ stdout from state into     │
  │     │ to a file                                 │ create_file                   │ content                    │    
  └─────┴───────────────────────────────────────────┴───────────────────────────────┴────────────────────────────┘
                                                                                                                      
  ---                                                                                                               
  Failure cases — executor must stop and report cleanly
                                                                                                                      
  ┌─────┬─────────────────────────────────────────┬───────────────────────────────────────────────────────────────┐
  │  #  │                  Task                   │                       Expected failure                        │   
  ├─────┼─────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤   
  │ 13  │ Read a file that does not exist         │ read_file raises, status=failed, log shows error              │
  ├─────┼─────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤   
  │ 14  │ Delete a file that does not exist       │ delete_file returns deleted: false, not an error — state      │   
  │     │                                         │ updated                                                       │   
  ├─────┼─────────────────────────────────────────┼───────────────────────────────────────────────────────────────┤   
  │ 15  │ Run a shell command that returns        │ return_code in state, executor treats as ok — caller decides  │   
  │     │ non-zero                                │                                                               │ 
  └─────┴─────────────────────────────────────────┴───────────────────────────────────────────────────────────────┘   
                                                                                                                    
  ---
  Subtask
                                                                                                                      
  ┌─────┬───────────────────────────────────────────────────────────────────┬─────────────────────────────────────┐
  │  #  │                               Task                                │            What it tests            │   
  ├─────┼───────────────────────────────────────────────────────────────────┼─────────────────────────────────────┤   
  │ 16  │ "Set up the project: create src/, create src/init.py, create      │ subtask reduction check, nested     │
  │     │ README.md"                                                        │ kernel                              │   
  └─────┴───────────────────────────────────────────────────────────────────┴─────────────────────────────────────┘   
  