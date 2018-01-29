all: readLP.cpp
	g++ readLP.cpp -std=c++11 -std=gnu++11 -rdynamic -lLpSensor -lpthread -ldl -lrt -o readLP 

debug: readLP.cpp
	g++ readLP.cpp -g -std=c++11 -std=gnu++11 -rdynamic -lLpSensor -lpthread -ldl -lrt -o readLP 


run: all
	./readLP
