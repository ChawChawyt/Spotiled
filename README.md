Hello

are u searching for a visualizer that makes ur music ur listening to on spotify be the color of visualizer on ur tech  

Spotiled is an app that uses ur Spotify Premium api and uses it as a color for the visualizer for ur mouse,keyboard,pc,motherboard,etc
if u dont have spotify premium the app wont work (u need spotify premium to get api)

if ur playing a music with green image that will be the visualizer color for the audio (if it cant reach ur api it will be solid white)

SETUP:
-1 Install OpenRGB 
-2 make OpenRGB SDK server "Online" by pressing the start server each time closing and opening openrgb the server should be as(server HOST: 0.0.0.0  server Port: 6742) or making it auto start on windows
| -2 how to turn on auto start server and Openrgb > open OpenRGB and click on settings tab scroll all the way down until u see (Start at Login) Check it (Set it to YES) and Check Start server Thats it for OpenRGB
-3 Open spotify Devoloper https://developer.spotify.com/ 
-4 Sign in 
-5 Click on ur name then click on Dashboard
-6 Check "I accept the Spotify Developer Terms of Service."
-7 Click OK 
-8 Verify ur email address if u didnt (REQUIRED) (click on verify open ur gmail and open the latest spotify verify email and then click on VERIFY it will take u to an website says "You're all set." then get back to the dashboard tab and refresh it)
-9 Click on Create app 
-10 write ur app name (Ex. Spotiled api)
-11 Write any description (Ex. app takes my music to a led)
-12 Redirect URL (Ex. http://127.0.0.1:8000/callback) (Documentation. https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)
-13 check Web Apis (if its blacked out for u just select anything then save and edit it again it will be showen)
-14 get ur Client id and client secret put them in  the .env file (if secret dosent show click on Show Client secret)
-15 Enjoy ur spotiled

If ur api dosent work and u runned the code it will say  UNSAFE it means the api entered in code is diffrent from the real one of ur account 
or use this documentation of how to get api: https://developer.spotify.com/documentation/web-api



Consider Reading the Others .mds file it might help u
If ur browser just shows UNSAFE forever and dosent stop just go to the Task manager (Ctrl + shift + esc) and search for Spotiled and click on End task it will stop To fix it and make it actually work make sure ur api is right

Spotiled is made with love

Credit
Spotiled is made By Chaw Chaw
Discord: @chaw_chawyt (Contact if u got Bugs, issues in the code or questions)
