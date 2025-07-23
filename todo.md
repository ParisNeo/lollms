new ui:

- OK - add edit button to bubbles
- OK- fix personalities
- OK - implement MCPS
- OK - add <think> block handling
- OK when generating, remove the input and show an animation instead
- OK in chatinput, when we press shift+enter replace the input with a code mirror with a toolbar
- OK generating title add spinner 
- OK fix delete message
- OK add information about left hops
- OK level : 0 to 5
- OK social activate/deactivate
- OK fix rag store building
- OK refresh discussion after generation
- OK add authenticate with email
- OK setup default page (new discussion/social networks)
- OK revamp RAG datastores interface to put it in its own view
- OK After stopping, save current status and refresh discussion
- OK auto title
- OK the steps must by default be closed
- OK the steps content must not exceed some length in the title mode
- OK use the name of the personality in bubble instead of assistant also add its icon if applicable
- OK override the copy button
- OK make sure the images stay after generation
- OK add a reload mcps to the admin page
- OK change the interface to use a left bar and move the return to interface to the bottom of that bar
- OK the modal looses information when another modal is shown
- OK user management page needs upgrade and bugfix
- OK make it possible to load any image file for mcp icons and set reduce their size automatically
- OK key generation for regular users
- OK centralize background processes
- OK add email sending to tasks

## SSO
- add applications/mcps log in with permissions via introspect

## Discussion:
- start/stop events must be collapsible, all that happens in between should be put inside in between
- make the tools sections collapsible
- support for equations with /[ /] format
- Add the possibility to use multiple bindings at once with different configurations
- fix the return key not sending the message
- add a upload to discussion button that uploads documents to the discussion and shows them to the user if needed
- fix branching
- add add/view/remove files to the discussion with options (full file or RAG for each)
- when cancelling the generation, refresh the discussion
- when the generation fails, refresh the discussion


### emailing system
- email users enhance with ai not working
- password reset views and fixing the lost password email problem


## services
- centralize icons management with a modal that allows preprocessing before building base64 png

  
## personalities
- Add personality sharing
- Revamp personalities management tools
- Add automatic generation of personalities
- Add rag for personality
- Add mcps for personality
- Add personality description to the list
- Add a system personalities management page for administrator
- Add personality maker AI
- FIx personality adding for users who are not admin ** IMPORTANT **
- Edit system prompt button
  
### bindings/models
- add alias for models


## user settings
- add activating realtime dms to the ui
  
## Rag settings 
- add RAG vectorizer setting to the user RAG settings
- add fast rag to the discussion

## cosmetics
- add customization of the webui
- add themes


## mcps
- change refresh mcps to reload mcps
- add a forgot my password button to the login modal that sends a notification to the administrator.
- refresh mcps must be converted to reload mcps
- add protection for MCP output

## background processes
- add purge to tasks
- add a new cleaning of unused uploaded files task
- add adding rag stores files to tasks management with access to file upload status.
- reload mcps
- starting apps

## apps
- add the possibility to use the domain name not just localhost
- set the domain name globally so that it can be used eaésily
- only show active apps in the apps list

- ### todoooo: fix embed function to use a specific model
- add current processes listing
- add a cleaning cron

## integrate lollms apps
- add the apps zoo to lollms_chat

## Scratchpad
- add summerize document to scratchpad ** IMPORTANT **
- fix the scratchpad loop ** IMPORTANT **
