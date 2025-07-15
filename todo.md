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

## Discussion:
- override the copy button
- make sure the images stay after generation
- when cancelling the generation, refresh the discussion
- make the tools sections collapsible
- support for equations with /[ /] format
- Add the possibility to use multiple bindings at once with different configurations
- fix the return key not sending the message
- if the generation fails, don't destroy the message
- Add a upload to discussion button that uploads documents to the discussion and shows them to the user if needed
- fix branching
- add tokens count to the chatinput
- add context progressbar with scratchpad summary button

## Admin
### emailing system
- user management page needs upgrade and bugfix
- email users enhance with ai not working

## personalities
- Add personality sharing
- Revamp personalities management tools
- Add automatic generation of personalities
- Add rag for personality
- Add mcps for personality
- Add personality description to the list
- Add a system personalities management page for administrator
  
### bindings/models
- add alias for models

### keys management and permissions
- key generation for regular users

## user settings
- add activating realtime dms to the ui
  
## Rag settings 
- add RAG vectorizer setting to the user RAG settings
- add fast rag to the discussion

## cosmetics
- add customization of the webui



## mcps
- change refresh mcps to reload mcps
- add a forgot my password button to the login modal that sends a notification to the administrator.
- refresh mcps must be converted to reload mcps
- add protection for MCP output

## background processes
- add current processes listing
- add a cleaning cron
