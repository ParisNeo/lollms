# Admin-Specific Tasks and Security

This section covers crucial tasks and security considerations unique to administrators. This content is dynamically added to your core help documentation.

---

## 1. Initial Setup and Security Hardening

After the very first installation, ensure these steps are completed for optimal security and functionality:

*   **Change Default Admin Password:**
    *   If you used an `initial_admin_user` in `config.toml`, immediately change that administrator's password in **Admin Panel > User Management**.
    *   *(Imagine an image here: Screenshot of editing an admin user's password in the Admin Panel.)*
*   **Configure HTTPS:**
    *   For production environments, always enable HTTPS in **Admin Panel > Global Settings > Server & HTTPS Settings**. Provide valid SSL certificate and key files. This encrypts all traffic between your users and the server.
    *   *(Imagine an image here: Screenshot of HTTPS settings in Admin Panel.)*
*   **Review Registration Mode:**
    *   Decide if new user registrations should be `direct` (auto-approved) or require `admin_approval` in **Admin Panel > Global Settings > Registration**. For public-facing instances, `admin_approval` is highly recommended.

---

## 2. Managing Users Effectively

*   **Approving Pending Users:**
    *   If `admin_approval` is enabled, regularly check **Admin Panel > User Management** for new users marked as "Inactive" with a "Pending Approval" status. Activate their accounts once reviewed.
    *   *(Imagine an image here: Screenshot of User Management table showing inactive/pending users.)*
*   **Role Management:**
    *   Grant or revoke `is_admin` status for users as needed. Be cautious with granting admin privileges.
*   **Monitoring Activity:**
    *   Use the "Last Seen" column in the user table to monitor user activity and identify inactive accounts.
*   **Password Resets:**
    *   If email sending is `manual`, you will receive notifications when users request password resets. Go to **Admin Panel > User Management**, edit the user, and use "Generate Reset Link" to provide a one-time link.
    *   *(Imagine an image here: Screenshot of generating a password reset link for a user.)*

---

## 3. Advanced Configuration & Optimization

*   **Global LLM Overrides:**
    *   In **Admin Panel > Global Settings > Global LLM Overrides**, you can force a specific LLM model and context size on all users. This is useful for:
        *   Ensuring everyone uses a powerful model for critical tasks.
        *   Standardizing resource usage across the server.
        *   Migrating users to a new default model.
    *   `Force Once` will set the user's preference once; `Force Always` will override their settings for every session.
    *   *(Imagine an image here: Screenshot of the Global LLM Overrides section in Admin Panel.)*
*   **Default Personalities & MCPs:**
    *   While users can add their own, consider adding frequently used or essential personalities and MCP servers as "System" types in **Admin Panel > Services**. This makes them available to all users by default.
*   **Backups:**
    *   Regularly back up your `data` directory (which contains the main application database `app_main.db`, user data, discussions, and SafeStore databases). A simple copy of the entire `simplified_lollms/data` folder is often sufficient.
*   **Disk Space Management:**
    *   Periodically use **Admin Panel > Import Tools > Purge Unused Uploads** to clean up temporary files.
    *   Monitor the size of user's `safestores` and `discussion_assets` directories.

---

## 4. Security Considerations

*   **Keep Software Updated:** Regularly check for updates to LoLLMs Chat and its dependencies. Updates often include security fixes.
*   **Strong Passwords:** Enforce strong password policies for your administrators and encourage users to use complex passwords.
*   **Network Access:** Restrict external network access to your LoLLMs server's port (e.g., 9642) using a firewall, only allowing necessary connections.
*   **Monitor Logs:** Pay attention to server logs for unusual activity or persistent errors.

---