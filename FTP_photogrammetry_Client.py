'''
*
* FTP Client to pull images from FTP server
* hosted on RPi for 3D image reconstruction.
*
* AUTHOR                    :   Mohammad Odeh
* DATE WRITTEN              :   Aug. 10th, 2018 Year of Our Lord
* LAST CONTRIBUTION DATE    :   Aug. 14th, 2018 Year of Our Lord
*
'''

# Import modules
from    time                        import  sleep                       # Add delays and wait times
from    threading                   import  Thread                      # Use threads to free up main()
from    subprocess                  import  Popen                       # Run batch script from within Python
from    ftplib                      import  FTP                         # For file transfer
import  paho.mqtt.client            as      mqtt                        # For general communications

# ************************************************************************
# ============================> DEFINE CLASS <============================
# ************************************************************************ 
class FTP_photogrammetery_Client( object ):

    def __init__( self, MQTT_broker_ip, username, password ):
        '''
        Initialize class
        '''
        
        self.MQTT_topics = { "IP_addr": "ftp/IP_addr",                  # For IP address communications
                             "status" : "ftp/status" ,                  # For handshakes communications
                             "images" : "ftp/images" ,                  # For image name communications
                             "general": "ftp/general" }                 # For things that are not in any previous category

        self.FTP_server_ip = None                                       # FTP IP address placeholder
        self.MQTT_client_setup( MQTT_broker_ip )                        # Setup MQTT client
        self.USER, self.PASS = username, password                       # FTP Username and Password
        self.run()                                                      # Run program
        
# ------------------------------------------------------------------------

    def MQTT_client_setup( self, addr ):
        '''
        Setup MQTT client
        '''

        # Error handling in case MQTT communcation setup fails (1/2)
        try:
            self.client = mqtt.Client( client_id="Client",              # Initialize MQTT client object
                                       clean_session=True )             # ...
            
            self.client.max_inflight_messages_set( 60 )                 # Max number of messages that can be part of network flow at once
            self.client.max_queued_messages_set( 0 )                    # Size 0 == unlimited

            self.client.will_set( self.MQTT_topics[ "status" ],         # "Last Will" message. Sent when connection is
                                  "CONERR_CLNT", qos=1, retain=False )  # ...lost (aka, disconnect was not called)

            self.client.reconnect_delay_set( min_delay=1,               # Min/max wait time in case of reconnection
                                             max_delay=2 )              # ...

            self.client.on_connect = self.on_connect                    # Assign callback functions
            self.client.on_message = self.on_message                    # ...
            
            self.client.connect( addr, port=1883, keepalive=60 )        # Connect to MQTT network
            self.t_client_loop=Thread(target=self.client_loop, args=()) # Start threaded MQTT data processing loop()
            self.t_client_loop.deamon = True                            # Allow program to shutdown even if thread is running
            self.t_client_loop.start()                                  # ...

            sleep( 0.5 )                                                # Allow some time for connection to be established
            
        # Error handling in case MQTT communcation setup fails (2/2)
        except Exception as e:
            print( "Could NOT setup MQTT communications" )              # Indicate error type and arguments
            print( "Error Type      : {}".format(type(e)))              # ...
            print( "Error Arguments : {}".format(e.args) )              # ...
            sleep( 1.0 )
            quit()                                                      # Shutdown entire program

# ------------------------------------------------------------------------

    def on_connect( self, client, userdata, flags, rc ):
        '''
        Callback function for when connection is established/attempted.
        
        Prints connection status and subscribes to ftp/# topic on
        successful connection.
        '''
        
        if  ( rc == 0 ):                                                # Upon successful connection
            print(  "MQTT Connection Successful"  )                     #   Subscribe to topic of choice
            self.client.subscribe( "ftp/#", qos=1 )                     #   ...

        elif( rc == 1 ):                                                # Otherwise if connection failed
            print( "Connection Refused - Incorrect Protocol Version" )  #   Troubleshoot

        elif( rc == 2 ):                                                # Same ^
            print( "Connection Refused - Invalid Client Identifier"  )  #   ...

        elif( rc == 3 ):
            print( "Connection Refused - Server Unavailable"         )

        elif( rc == 4 ):
            print( "Connection Refused - Bad Username or Password"   )

        elif( rc == 5 ):
            print( "Connection Refused - Not Authorized"             )

        else:
            print( "Troubleshoot RPi   - Result Code {}".format(rc)  )
            print( "Terminating Program" )
            quit()

# ------------------------------------------------------------------------

    def on_message( self, client, userdata, msg ):
        '''
        Callback function for when a message is received.
        '''
        
        if( msg.topic == self.MQTT_topics[ "IP_addr" ] ):               # If we receive something on the IP topic
            inData = msg.payload.decode( "utf-8" )                      #   Decode payload
            if( len(inData) < 4 ): pass                                 #   Check it is a valid IP address
            else:                                                       #   If IP address is valid
                self.FTP_server_ip = inData                             #       Store IP address
                self.client.publish( self.MQTT_topics[ "status" ],      #       Send SOH to indicate that we are ready
                                     "SOH", qos=1, retain=False  )      #       ...
                    
                print( "Using IP: {}\n".format(self.FTP_server_ip) )    #       [INFO] ...

        elif( msg.topic == self.MQTT_topics[ "images" ] ):              # If we receive something on the images topic
            img_name = msg.payload.decode( "utf-8" )                    #   Decode image name
            if( img_name == '' ): pass                                  #   If empty string (used to clear retained messages), pass
            else: self.get_file( img_name )                             #   Else, retrieve it from FTP folder on server

        elif( msg.topic == self.MQTT_topics[ "status" ] ):              # If we receive something on the status topic
            status = msg.payload.decode( "utf-8" )                      #   Decode it and determine next action

            if( status == "EOT" ):                                      #   If end of transmission is indicated
                print( "Disconnectiong MQTT" ) ,                        #       [INFO] ...
                self.client.publish( self.MQTT_topics[ "status" ],      #       Send EOT to inform server to
                                     "EOT", qos=1, retain=False  )      #       ...shuwtdown MQTT client as
                self.loop = False                                       #       Set loop flag to FALSE
                sleep( 0.10 )                                           #       Allow time for state of flag to change
                self.client.disconnect()                                #       Disconnect MQTT client
                print( "...DONE!" )                                     #       [INFO] ...

            else                 : pass
        
        else: pass

# ------------------------------------------------------------------------

    def client_loop( self ):
        '''
        A simple, basic workaround for the MQTT's library stupid 
        threaded implementation of loop() that doesn't really work.
        '''
        
        self.loop = True                                                # Boolean loop flag
        while( self.loop ):                                             # Loop 43va while loop flag is TRUE
            self.client.loop( timeout=1.0 )                             #   Pool messages queue for new data
        
# ------------------------------------------------------------------------

    def get_file( self, file_name ):
        '''
        Get file from FTP directory

        INPUT:
            - file_name: Name of file we want to get
        '''

        print( "Retrieving {}".format(file_name) ) ,                    # [INFO] ...
        
        localfile = r".\imgs\{}".format(file_name)                      # Specify image storage path
        with open( localfile, 'wb' ) as f:                              # Open file for writing
            self.ftp.retrbinary( "RETR "+file_name,                     # Retrieve file from FTP directory and copy
                                 f.write, 2048 )                        # contents to localfile at 2048 bytes chunks
            
        print( "...DONE!" )                                             # [INFO] ...

# ------------------------------------------------------------------------

    def run( self ):
        '''
        Main thread
        '''
        
        sleep( 0.5 )                                                    # Sleep for stability
        print( "Client Initialized" )                                   # [INFO] ...

        print( "Waiting for FTP IP address" )                           # [INFO] ...
        cntr = 0                                                        # Counter for displaying "waiting" dots
        while( self.FTP_server_ip is None ):                            # Wait until we get a vlid IP address
            sleep( 1 )                                                  #   ...
            print( '.' ) ,                                              #   ...
            cntr += 1                                                   #   ...
            if( cntr == 15 ):                                           #   If we already printed 15 dots
                cntr = 0                                                #       Reset counter
                print( '' )                                             #       Start a new line
        if( cntr is not 0 ): print( '' )                                # Start a new line

        print( "Client Ready\n" )                                       # [INFO] ...
        
        self.ftp = FTP( self.FTP_server_ip )                            # Connect to host using default port
        self.ftp.login( FTP_USER, FTP_PASS )                            # Login as a known user (NOT anonymous user)

        self.ftp.cwd( "/home/pi/FTP/" )                                 # Change current working directory to FTP directory
##        self.ftp.retrlines( "LIST" )                                    # List contents of FTP directory (make sure things are working)

        while( self.loop ):                                             # While we are still receiving data (images)
            sleep( 0.1 )                                                #   Stay in loop to waste time

##        print( "Running VisualSFM" ) ,                                  # [INFO] ...
##        p = Popen( [r".\main.bat"] )                                    # Call batch file with VisualSFM commands
##        stdout, stderr = p.communicate()                                # ...
##        print( "...DONE!" )                                             # {INFO] ...
        
# ************************************************************************
# ===========================> SETUP  PROGRAM <===========================
# ************************************************************************      

MQTT_IP_ADDRESS     = "192.168.42.1"                                    # IP address for MQTT broker
FTP_USER, FTP_PASS  = "pi", "raspberry"                                 # FTP login credentials
##FTP_USER, FTP_PASS  = "root", "dietpi"                                  # FTP login credentials

prog = FTP_photogrammetery_Client( MQTT_IP_ADDRESS, FTP_USER, FTP_PASS )# Start program
