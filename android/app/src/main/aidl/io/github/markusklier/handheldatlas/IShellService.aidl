package io.github.markusklier.handheldatlas;

// Runs inside the Shizuku user service (shell uid). Only Atlas' own process can bind it.
interface IShellService {
    void destroy() = 16777114;   // reserved by Shizuku
    String exec(String command, int timeoutMs) = 1;
}
