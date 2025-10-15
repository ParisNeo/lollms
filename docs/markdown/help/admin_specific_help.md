# Administrator Guide

This content is exclusively for administrators.

<h2 id="user-management">User Management</h2>

Navigate to **Admin Panel -> Users** to manage all user accounts on the platform. From this view, you can:

-   **View All Users:** See a list of all registered users, their status (active/inactive), and last activity.
-   **Approve New Users:** If registration is set to `admin_approval`, new users will appear here as inactive. You must manually activate their accounts.
-   **Edit Users:** Grant or revoke admin privileges, change user details, and reset passwords.
-   **Delete Users:** Permanently remove a user and all their associated data from the system.

<h2 id="global-settings">Global Settings</h2>

The **Admin Panel -> Global Settings** section allows you to configure system-wide behavior. Key settings include:

-   **Registration:** Enable or disable new user registrations and set the approval mode.
-   **Default Model:** Set the default LLM model that new users will be assigned.
-   **Force Model:** Override all user model selections with a specific model, useful for testing or dedicated-purpose deployments.
-   **API Services:** Enable or disable the OpenAI-compatible API endpoints.