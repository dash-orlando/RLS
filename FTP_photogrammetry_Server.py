'''
*
* FTP server for capturing and storing images that are
* to be pulled by client for 3D image reconstruction.
*
* AUTHOR                    :   Mohammad Odeh
* DATE WRITTEN              :   Aug. 10th, 2018 Year of Our Lord
* LAST CONTRIBUTION DATE    :   Aug. 14th, 2018 Year of Our Lord
*
'''

# Import modules
from    time                        import  sleep, time                 # Add delays and wait times
from    threading                   import  Thread                      # Use threads to free up main()
from    picamera                    import  PiCamera                    # Take pictures
from    commands                    import  getoutput                   # Get output of commands issued in CLI
import  paho.mqtt.client            as      mqtt                        # For general communications

# ************************************************************************
# ============================> DEFINE CLASS <============================
# ************************************************************************ 
class FTP_photogrammetery_Server( object ):

    def __init__( self, MQTT_broker_ip, IMG_NUM, IMG_INTERVAL ):
        '''
        Initialize class

        INPUTS:
             - MQTT_broker_ip: IP address of MQTT broker
             - IMG_NUM       : Number of images we would like to take
             - IMG_INTERVAL  : Interval at which we want to take imgs
        '''
        
        self.MQTT_topics = { "IP_addr": "ftp/IP_addr",                  # For IP address communications
                             "status" : "ftp/status" ,                  # For handshakes communications
                             "images" : "ftp/images" ,                  # For image name communications
                             "general": "ftp/general" }                 # For things that are not in any previous category
        
        self.imgs_quantity = IMG_NUM                                    # Store how many images we want
        self.imgs_interval = IMG_INTERVAL                               # Store the interval of acquisition

        self.ready = False                                              # Flag indicating whether or not we are ready to take picture
        self.MQTT_client_setup( MQTT_broker_ip )                        # Setup MQTT client
        self.get_IP()                                                   # Get FTP IP address and send to client
        self.run()                                                      # Run program
        
# ------------------------------------------------------------------------

    def MQTT_client_setup( self, addr ):
        '''
        Setup MQTT client
        '''

        # Error handling in case MQTT communcation setup fails (1/2)
        try:
            self.client = mqtt.Client( client_id="Server",              # Initialize MQTT client object
                                       clean_session=True )             # ...
            
            self.client.max_inflight_messages_set( 60 )                 # Max number of messages that can be part of network flow at once
            self.client.max_queued_messages_set( 0 )                    # Size 0 == unlimited

            self.client.will_set( self.MQTT_topics[ "status" ],         # "Last Will" message. Sent when connection is
                                  "CONERR_SRVR", qos=1, retain=False )  # ...lost (aka, disconnect was not called)

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

        print( "Clearing retained messages on initial run" ) ,          # [INFO] ...
        for _, topic in self.MQTT_topics.iteritems():                   # Clear ALL retianed messages in all the sub-topics within
            self.client.publish( topic, '', qos=1, retain=True )        # the FTP main topic by sending an empty string
        print( "...DONE!\n" )                                             # [INFO] ...
        
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
        
        if( msg.topic == self.MQTT_topics[ "status" ] ):                # If we receive something on the status topic
            status = msg.payload.decode( "utf-8" )                      #   Decode it and determine next action

            if  ( status == "SOH" ) : self.ready = True                 #   If we get an SOH, we are ready to proceed
            elif( status == "EOT" ) :                                   #   If end of transmission is indicated
                print( "Disconnecting MQTT" ) ,                         #       [INFO] ...
                self.loop = False                                       #       Set loop flag to FALSE
                sleep( 0.10 )                                           #       Allow time for state of flag to change
                self.client.disconnect()                                #       Disconnect MQTT client
                print( "...DONE!" )                                     #       [INFO] ...
                
            else                    : pass
        
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

    def get_IP( self ):
        '''
        Obtain IP address to be used for accessing the FTP server
        '''

        ip = getoutput( "hostname -I" )                                 # Run 'hostname -I'
        ip = ip.split( ' ' )                                            # Split on a space basis

        for i in range( 0, len(ip) ):                                   # Make sure we are using a valid
            if( ip[i][0]=='1' and ip[i][1]=='9' and ip[i][2]=='2' ):    # IP address ...
                ip = ip[i]                                              # ...
                break                                                   # ...
           
        print( "Using IP: {}\n".format(ip) )                            # [INFO] ...

        self.client.publish( self.MQTT_topics[ "IP_addr" ],             # Transmit FTP IP address
                             ip, qos=1, retain=True )                   # over MQTT

# ------------------------------------------------------------------------

    def take_image( self, img_num ):
        '''
        Capture image with a specific name and publish said name
        to MQTT for client to retrieve later on through FTP

        INPUT:
            - img_num: Image number
        '''

        img_name = "image{}.jpg".format( img_num )                      # Construct image name
##        img_path = "/home/pi/FTP/{}".format( img_name )                 # Define image's path ( FTP folder on Raspbian )
        img_path = "/mnt/dietpi_userdata/Pictures{}".format( img_name ) # Define image's path ( FTP folder on DietPi )
        
        print( "Sending {}".format(img_name) ) ,                        # [INFO] ...
        
        with PiCamera() as cam:                                         # Capture image
            cam.capture( img_path )                                     # ...

        self.client.publish( self.MQTT_topics[ "images" ],              # Publish image's name to MQTT for retrieval
                             img_name, qos=1 )                          # ...
            
        print( "...DONE!" )                                             # [INFO] ...

# ------------------------------------------------------------------------

    def run( self ):
        '''
        Main thread
        '''
        
        sleep( 0.5 )                                                    # Sleep for stability
        print( "FTP Server Initialized" )                               # [INFO] ...

        print( "Waiting for client to be ready" )                       # [INFO] ...
        cntr = 0                                                        # Counter for displaying "waiting" dots
        while( self.ready == False ):                                   # Wait until we are ready
            sleep( 1 )                                                  #   ...
            print( '.' ) ,                                              #   ...
            cntr += 1                                                   #   ...
            if( cntr == 15 ):                                           #   If we already printed 15 dots
                cntr = 0                                                #       Reset counter
                print( '' )                                             #       Start a new line
        print( '' )                                                     # Start a new line
        
        for i in range( self.imgs_quantity ):                           # Take as many images as we specified
            self.take_image( i )                                        #   ...
            
            timer = time()                                              #   Timer to waste time in order to capture at required interval
            while( time() - timer < self.imgs_interval ): pass          #   ...
            
        print( "\nClearing retained messages prior to exit" ) ,         # [INFO] ...
        for _, topic in self.MQTT_topics.iteritems():                   # Clear ALL retianed messages in all the sub-topics within
            self.client.publish( topic, '', qos=1, retain=True )        # the FTP main topic by sending an empty string
        print( "...DONE!" )                                             # [INFO] ...

        self.client.publish( self.MQTT_topics[ "status" ],              # Send an EOT to inform client that he can proceed
                             "EOT", qos=1 )                             # into the image processing & 3D reconstruction
        
# ************************************************************************
# ===========================> SETUP  PROGRAM <===========================
# ************************************************************************      

MQTT_IP_ADDRESS     = "192.168.42.1"                                    # IP address for MQTT broker
NUMBER, FREQUENCY   = 5, 1                                              # Number & frequency of images           
prog = FTP_photogrammetery_Server( MQTT_IP_ADDRESS, NUMBER, FREQUENCY ) # Start program
