#include <cstdio>

#include <thread>
#include <LpmsSensorI.h>
#include <LpmsSensorManagerI.h>

#include <stdint.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <iostream>
#include <sys/time.h>                
#include <errno.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
using namespace std;

// C
#include <stdlib.h>


char formatString[] = 
"{\"id\": %d, "
 "\"iid\": %d, "
 "\"data\": "
    "{ \"quat\": [%f, %f, %f, %f], "
      "\"offset\": [%f, %f, %f, %f], "
      "\"acc\": [%f, %f, %f], "
      "\"mag\": [%f, %f, %f], "
      "\"gyr\": [%f, %f, %f], "
      "\"bar\": %f, "
      "\"timestamp\": %f "
    "}"
"}"; 


struct sensorInfo {
    struct timeval t1, t2, t_temp;
    double elapsedTime;
    LpmsSensorI *sensor;
    int count;
};

char unix_socket[] = "/tmp/sensor_producer";
float frequency = 133;

sensorInfo *sInfo; // Array
int num_sensors = 0;
uint32_t header_size = 0;
float period = 1000.0 / frequency;

int main(int argc, char *argv[])
{
    /* Connect both or just one? */
	if(argc < 2){
		printf("Error! Need at least one arg.\n"
               "Example: ./LpmsSimpleExample 00:06:66:AA:BB:CC\n\n"
              );
		exit(-1);
    }

    // Socket
	int s, len;

   	if ((s = socket(AF_UNIX, SOCK_STREAM, 0)) == -1) {
        perror("socket");
        exit(1);
    }

	fprintf(stderr, "Trying to connect to message bus ...\n");

	struct sockaddr_un remote;
	remote.sun_family = AF_UNIX;
	strcpy(remote.sun_path, unix_socket);
	len = strlen(remote.sun_path) + sizeof(remote.sun_family);
	if (connect(s, (struct sockaddr *)&remote, len) == -1) {
        perror("connect");
        fprintf(stderr, "Tried connecting to unix socket at %s\n", remote.sun_path);
        exit(1);
    }
	fprintf(stderr, "Connected to message bus.\n");
	
    
    // Gets a LpmsSensorManager instance
	LpmsSensorManagerI* manager = LpmsSensorManagerFactory();
   
    // Try to connect 
    ImuData data[2];
	if (argc >= 1){
		if ( strlen(argv[1]) == 17){
            num_sensors = 1;
            sInfo = (sensorInfo*)calloc(num_sensors, sizeof(sensorInfo));
            fprintf(stderr, "Trying to connect to '%s'...\n", argv[1]);
            LpmsSensorI* test = manager->addSensor(DEVICE_LPMS_B, argv[1] );
            sInfo[0].sensor = test; 
        } else {
            printf("Unknown argument.\n");
            close(s);
            delete(manager);
            exit(1);
        }
	} 
    
    // Wait to connect	
    for (int i = 0; i < num_sensors; ++i) {
        while(sInfo[i].sensor->getConnectionStatus() != SENSOR_CONNECTION_CONNECTED){
            printf("Waiting for sensor %d/%d\n", i, num_sensors);
            std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        }
        gettimeofday(&sInfo[i].t1, NULL);
        sInfo[i].count = 0;
    }
	
	
    char buffer[1024];
    bzero(buffer, 1024);
    
    uint32_t hsize  = 10;
    int sent = 0;
    int ret  = 0;

    while(1) {
        // Get data for each sensor
        for(int i = 0; i < num_sensors; i++){
            // Checks, if conncted
            if (
                    sInfo[i].sensor->getConnectionStatus() == SENSOR_CONNECTION_CONNECTED &&
                    sInfo[i].sensor->hasImuData()
               ) {
                // Reads quaternion data
                // Shows data
                gettimeofday(&sInfo[i].t2, NULL);
                sInfo[i].elapsedTime = (sInfo[i].t2.tv_sec - sInfo[i].t1.tv_sec) * 1000.0;      // sec to ms
                sInfo[i].elapsedTime += (sInfo[i].t2.tv_usec - sInfo[i].t1.tv_usec) / 1000.0;   // us to ms

				// Read sensor data if the time has come, according to the configured frequency
                if (sInfo[i].elapsedTime >= period) {

                    data[i] = sInfo[i].sensor->getCurrentData();

					// See sensor documentation for return signature of getCurrentData()
                    sprintf(buffer, formatString,
                            0, // id
                            i, // iid
                            data[i].q[0],//w
                            data[i].q[1],//x
                            data[i].q[2],//y
                            data[i].q[3],//z
                            0.0,//x 
                            0.0,//y
                            0.0,//z
                            0.0,//w
                            data[i].a[0],//x accel
                            data[i].a[1],//y
                            data[i].a[2],//z
                            data[i].b[0],//x mag
                            data[i].b[1],//y
                            data[i].b[2],//z
                            data[i].g[0],//x gyr
                            data[i].g[1],//y
                            data[i].g[2],//z
                            data[i].pressure,//baro
                            data[i].timeStamp//timestamp
                           );
                    header_size = strlen(buffer);
                    if( header_size > 0){
                        header_size = htonl(header_size);

                        sent = 0;
                        ret = 0;
                        while ( sent < sizeof(header_size)) {
                            ret = send(s, (const void*)&header_size, sizeof(uint32_t), 0);
                            if (ret == -1){
                                perror("send");
                                exit(1);
                            }else{
                            }
                            sent += ret;
                        }
                        sent = 0;
                        ret = 0;
                        while ( sent < strlen(buffer) ){
                            ret = send(s, sent+buffer,strlen(buffer)-sent, 0);
                            if (ret == -1){
                                perror("send");
                                exit(1);
                            }else{
                            }

                            sent += ret;
                        }
                    }


                    sInfo[i].t_temp = sInfo[i].t1;
                    sInfo[i].t1 = sInfo[i].t2;
                    sInfo[i].t2 = sInfo[i].t_temp;

                    if(sInfo[i].count++ > 100){
                        fprintf(stderr,"ID: %d ms: %f, f= %f", i, sInfo[i].elapsedTime, 1/(sInfo[i].elapsedTime/1000));
                        fprintf(stderr,"Timestamp=%f, qW=%f, qX=%f, qY=%f, qZ=%f\n", 
                                data[i].timeStamp, data[i].q[0], data[i].q[1], data[i].q[2], data[i].q[3]);
                        sInfo[i].count = 0;
                    }
                }            
			}
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
	}

	// Removes the initialized sensor(s)
    for(int i = 0; i < num_sensors; i++){
        manager->removeSensor(sInfo[i].sensor);
    }
		
	// Deletes LpmsSensorManager object 
	delete manager;

	// Close socket
	close(s);

    // Free sInfo structures
    free(sInfo);

	return 0;
}
