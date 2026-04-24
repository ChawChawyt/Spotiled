## Hey, are you searching for a spotify music visualizer?  
### Then check out Spotiled!  
### Spotiled is an app that uses the Spotify _**Premium**_ api and uses it as a color for the visualizer for your rgb periperals

For example, if you are playing music with a green cover art, that color will be set as the audio color, HOWEVER if Spotiled cant reach the api the color will remain solid white.

## SETUP:
 1. **Install OpenRGB**
 2. make **OpenRGB SDK server "Online"** by pressing the start server each time closing and opening openrgb the server should be as(server HOST: 0.0.0.0  server Port: 6742) or **making it auto start on windows**
 3. turn on auto start server and Openrgb > open OpenRGB and click on **settings tab** scroll all the way down until u see (**Start at Login**) Check it (**Set it to YES**) and Check Start server Thats it for OpenRGB
 4. **Open spotify Developers** https://developer.spotify.com/
 5. **Sign in**
 6. Click on ur **name** then click on **Dashboard**
 7. Check **"I accept the Spotify Developer Terms of Service."**
 8. Click **OK**
 9. **Verify ur email address** if u didnt (**REQUIRED**) (click on verify open ur gmail and open the latest spotify verify email and then click on **VERIFY** it will take u to an website says "You're all set." then get back to the dashboard tab and **refresh it**)
 10. Click on **Create app**
 11. write ur **app name** (Ex. Spotted bee)
 12. Write any **description** (Ex. app takes my music to a led)
 13. **Redirect URL** (Ex. http://127.0.0.1:8000/callback) (Documentation. https://developer.spotify.com/documentation/web-api/concepts/redirect_uri)
 14. check **Web Apis** (if its blacked out for u just select anything then save and edit it again it will be **the show**)  
 15. get ur **Client id** and **client secret** put them in  the **.env file** (if secret dosent show click on **Show Client secret**)  
 16. **Enjoy ur spotiled**

If your api dosent work and you ran the code it will output  **UNSAFE** . This means the api entered in the code is diffrent from the one on your account.    
Use this -> https://developer.spotify.com/documentation/web-api  | to learn how to get your api key  



Consider Reading the rest of the MD files located in the README directory.  
If your browser just shows **UNSAFE** forever and dosent stop, just go to **Task manager** (**Ctrl + shift + esc**) and search for Spotiled and click on **End task** it will stop.  
To fix it and make it actually work **make sure ur api is right**  

Made with **love** by **Chaw_Chaw**    
Discord: **@chaw_chawyt** (Contact for: **Bugs**, **issues**, or **questions**)  
Thank for **@bkgrnd** for making this Readme!
