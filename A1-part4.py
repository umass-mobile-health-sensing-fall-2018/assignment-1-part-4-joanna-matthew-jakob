import socket
import sys
import json
import threading
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
import numpy as np
from scipy.ndimage.interpolation import shift
from scipy.signal import argrelextrema

# TODO: Replace the string with your user ID
user_id = "Potassium"
window_counter = 250
static_mags = np.zeros(250)
static_indices = np.zeros(250)
# TODO: (optional) Initialize any global variables you may need for your step detection algorithm
#################   Begin Server Connection Code  ####################

def authenticate(sock):
    """
    Authenticates the user by performing a handshake with the data collection server.
    
    If it fails, it will raise an appropriate exception.
    """
    msg_request_id = "ID"
    msg_authenticate = "ID,{}\n"
    msg_acknowledge_id = "ACK"
    
    message = sock.recv(256).strip().decode('ascii')
    if (message == msg_request_id):
        print("Received authentication request from the server. Sending authentication credentials...")
    else:
        print(type(message))
        print("Authentication failed!")
        raise Exception("Expected message {} from server, received {}".format(msg_request_id, message))
    sock.send(msg_authenticate.format(user_id).encode('utf-8'))

    try:
        message = sock.recv(256).strip().decode('ascii')
    except:
        print("Authentication failed!")
        raise Exception("Wait timed out. Failed to receive authentication response from server.")
        
    if (message.startswith(msg_acknowledge_id)):
        ack_id = message.split(",")[1]
    else:
        print("Authentication failed!")
        raise Exception("Expected message with prefix '{}' from server, received {}".format(msg_acknowledge_id, message))
    
    if (ack_id == user_id):
        print("Authentication successful.")
        sys.stdout.flush()
    else:
        print("Authentication failed!")
        raise Exception("Authentication failed : Expected user ID '{}' from server, received '{}'".format(user_id, ack_id))
        
def recv_data():
    """
    Continuously receives data from the server and calls detectSteps
    """
    global receive_socket
    global t, value   # global variables to hold incoming timestamp and values
    global tvals, vals  # global value buffers to hold a stream of timestamp and values. Will be used to plot an interval of data

    previous_json = ''

    while True:
        try:
            message = receive_socket.recv(1024).strip().decode('ascii')
            json_strings = message.split("\n")
            json_strings[0] = previous_json + json_strings[0]
            for json_string in json_strings:
                try:
                    data = json.loads(json_string)
                except:
                    previous_json = json_string
                    continue
                previous_json = '' # reset if all were successful
                sensor_type = data['sensor_type']
                if (sensor_type == u"SENSOR_PPG"):
                    t=data['data']['t']
                    value=data['data']['value']
                    
                    #Shift new data into the numpy plot buffers 
                    vals = shift(vals, 1, cval=0)
                    vals[0] = value

                    #Shift old steps backwards
                    # global stepindices
                    # stepindices = shift(stepindices, 1, cval=False)
                    
            sys.stdout.flush()
            detectSteps(t,value,value,value)
        except KeyboardInterrupt: 
            # occurs when the user presses Ctrl-C
            print("User Interrupt. Quitting...")
            break
        
        except Exception as e:
            # ignore exceptions, such as parsing the json
            # if a connection timeout occurs, also ignore and try again. Use Ctrl-C to stop
            # but make sure the error is displayed so we know what's going on
            if (str(e) != "timed out"):  # ignore timeout exceptions completely       
                print(e)
            pass

#################   End Server Connection Code  ####################

def detectSteps(time,x_in,y_in,z_in):
    """
    Accelerometer-based step detection algorithm.
    
    In this assignment, you will implement a step detection algorithm for
    live accelerometer data collected from your Android app. This may be 
    functionally equivalent to your step detection algorithm for static data
    if you like. Remember to use the global keyword if you would like to 
    access global variables such as counters or buffers. 
    """
    global window_counter
    # input variables for this method seem to be useless/optional ???
    if window_counter != 0:  # wait until entire new window's worth of data has been acquired
        window_counter -= 1
        return

    window_counter = 250  # reset the window counter variable
    # TODO: Step detection algorithm
    global stepindices
    global magvals
    global static_mags
    static_mags = np.array(magvals) # have to reinitialize array otherwise the pointers for static_mags and magvals become the same

    # Implement high-pass filter
    from scipy.signal import butter, filtfilt
    # Filter requirements.
    order = 5
    fs = 50.0  # sample rate, Hz
    cutoff = 3  # desired cutoff frequency of the filter, Hz. MODIFY AS APPROPROATE

    # Create the filter.
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='highpass', analog=False)

    # Apply the butterworth filter on the signal
    filtered_signal = filtfilt(b, a, static_mags)

    # RUN STEP DETECTION
    step_indices = list(map(int, step_detection(filtered_signal)))  # get indices of steps in range 0-249

    steps_times = np.take(tvals, step_indices)  # get x values for plotting
    steps_vals = np.take(filtered_signal, step_indices)  # get y values for plotting

    ax3.clear()
    ax3.plot(tvals, filtered_signal, label="filtered signal", linewidth=2)
    ax3.scatter(steps_times, steps_vals, label="steps", marker="o", color="r")
    ax3.legend(loc="upper right")
    ax3.set_title('Magnitude Intervals With Steps')
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('Acceleration (m/s^2)')
    ax3.set_ylim(-2,2)

    return


def step_detection(signal):
    # returns a list of indices corresponding to steps (in range of 0-249)]
    maxima = argrelextrema(signal, np.greater)
    maxima = maxima[0]
    minima = argrelextrema(signal, np.less)
    minima = minima[0]
    peaks = list()
    j = 0
    
    for i in minima:
        if signal[i] > -0.1 or ((signal[maxima[j+1]] < 0) and j!= (len(signal)-1)):
            j = j + 1
        else:
            peaks.append(i)
    
    print("Heart Rate: ", len(peaks)*6)

    return np.asarray(peaks)


def animate(i):
    """
    Helper function that animates the canvas
    """
    global tvals, vals # global value buffers that we are appending to in recv_data
    
    try:
        ax1.clear()
        ax2.clear()
        
        # plotting live values of acceleration in the x, y and z directions
        ax1.plot(tvals, vals)
        ax1.set_title('Real Time Raw Signal')
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylim(230,260)
        
        # TODO: add code to plot magnitude on axis 2. Also add markers to the plot at points where steps are detected.
        global magvals
        global stepindices

        # Implement high-pass filter
        from scipy.signal import butter, filtfilt
        # Filter requirements.
        order = 5
        fs = 50.0  # sample rate, Hz
        cutoff = 3  # desired cutoff frequency of the filter, Hz. MODIFY AS APPROPROATE

        # Create the filter.
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        b, a = butter(order, normal_cutoff, btype='highpass', analog=False)

        # Apply the butterworth filter on the signal
        magvals = filtfilt(b, a, vals)
        magvals = magvals - np.mean(magvals)

        ax2.plot(tvals, magvals, linewidth=2)   # plot data
        
        # boilerplate code for the layout of graph 2
        ax2.set_title('Real Time Filtered Signal')
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylim(-2,2)

    except KeyboardInterrupt:
        quit()
        
try:
    # This socket is used to receive data from the data collection server
    receive_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    receive_socket.connect(("none.cs.umass.edu", 8888))

    # ensures that after 1 second, a keyboard interrupt will close
    receive_socket.settimeout(1.0)
    
    print("Authenticating user for receiving data...")
    sys.stdout.flush()
    authenticate(receive_socket)
    
    print("Successfully connected to the server! Waiting for incoming data...")
    sys.stdout.flush()
        
    previous_json = ''

    t = 0
    value = 0
    
    # numpy array buffers used for visualization
    tvals = np.linspace(0,10,num=250)
    vals = np.zeros(250)
    magvals = np.zeros(250)
    stepindices = np.zeros(250,dtype='int')
    
    socketThread = threading.Thread(target=recv_data, args=())
    socketThread.start()
    
    
    #Setup the matplotlib plotting canvas
    grid = plt.GridSpec(2, 2, wspace=0.4, hspace=0.3)

    style.use('fivethirtyeight')
    
    fig = plt.figure(figsize=(12, 6))
    ax1 = fig.add_subplot(grid[0,0])
    ax2 = fig.add_subplot(grid[0,1])

    # for the static window
    ax3 = fig.add_subplot(grid[1,0:])
    
    # Point to the animation function above, show the plot canvas
    ani = animation.FuncAnimation(fig, animate, interval=20)
    plt.show()

except KeyboardInterrupt: 
    # occurs when the user presses Ctrl-C
    print("User Interrupt. Quitting...")
    plt.close("all")
    quit()