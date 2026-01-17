/*
 * Vulnerable C Program - Test Fixture for Joern Dataflow Analysis
 * 
 * This program contains intentional security vulnerabilities
 * for testing KnowGraph's taint analysis capabilities.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// SQL Injection vulnerability
void vulnerable_login(char *username, char *password) {
    char query[256];
    
    // VULNERABLE: Direct string concatenation
    sprintf(query, "SELECT * FROM users WHERE username='%s' AND password='%s'", 
            username, password);
    
    printf("Executing query: %s\n", query);
    // Imagine this executes the SQL query
}

// Command Injection vulnerability
void vulnerable_ping(char *hostname) {
    char command[256];
    
    // VULNERABLE: User input in shell command
    sprintf(command, "ping -c 4 %s", hostname);
    
    system(command);  // DANGEROUS!
}

// Buffer Overflow vulnerability
void vulnerable_copy(char *user_input) {
    char buffer[64];
    
    // VULNERABLE: No bounds checking
    strcpy(buffer, user_input);
    
    printf("Copied: %s\n", buffer);
}

// Path Traversal vulnerability
void vulnerable_read_file(char *filename) {
    FILE *fp;
    char buffer[1024];
    
    // VULNERABLE: No path validation
    fp = fopen(filename, "r");
    
    if (fp != NULL) {
        fread(buffer, 1, sizeof(buffer), fp);
        fclose(fp);
    }
}

// Safe function using parameterized approach
void safe_login(char *username, char *password) {
    // This would use prepared statements in real code
    printf("Safe login for user: %s\n", username);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s <username>\n", argv[0]);
        return 1;
    }
    
    // TAINT FLOW: argv[1] -> vulnerable_login
    vulnerable_login(argv[1], "password123");
    
    // TAINT FLOW: argv[1] -> vulnerable_ping
    vulnerable_ping(argv[1]);
    
    // TAINT FLOW: argv[1] -> vulnerable_copy
    vulnerable_copy(argv[1]);
    
    return 0;
}
