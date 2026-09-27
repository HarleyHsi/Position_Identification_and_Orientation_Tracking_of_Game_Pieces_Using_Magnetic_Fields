/* This is the program responsible for establishing I2C connection between MLX90393 sensors and ESP32 chips
Written by Hossein Ali Hooseini
Supports up to 9 sensors via a PCA9548A mux (8 channels, with one channel able to
host two sensors at different I2C addresses).
*/
#include <Wire.h>
#include "Adafruit_MLX90393.h"

#define PCA9548A_ADDR 0x70
#define I2C_SDA       21
#define I2C_SCL       22

// ---------------------------------------------------------------------------
// Sensor map: one row per sensor.
//   channel = PCA9548A channel, 0-7
//   addr    = MLX90393 I2C address, or 0 to auto-detect on that channel
//
// A PCA9548A only has 8 channels, so the 9th sensor must share a channel with
// another one and use a different I2C address (set by the A0/A1 pins).
// Uncomment the last row when the 9th sensor is wired in, and give BOTH sensors
// on the shared channel an explicit address.
// ---------------------------------------------------------------------------
struct SensorSlot {
  uint8_t channel;
  uint8_t addr;
};

SensorSlot sensorSlots[] = {
  {0, 0},
  {1, 0},
  {2, 0},
  {3, 0},
  {4, 0},
  {5, 0},
  {6, 0},
  {7, 0},
  {0, 0x0D},  
};

const uint8_t NUM_SENSORS = sizeof(sensorSlots) / sizeof(sensorSlots[0]);

const uint8_t MLX_POSSIBLE_ADDRS[] = {0x0C, 0x0D, 0x0E, 0x0F};
const uint8_t NUM_POSSIBLE_ADDRS = sizeof(MLX_POSSIBLE_ADDRS) / sizeof(MLX_POSSIBLE_ADDRS[0]);

Adafruit_MLX90393 sensors[NUM_SENSORS];
bool    sensorActive[NUM_SENSORS];
uint8_t sensorAddr[NUM_SENSORS];

void selectMuxChannel(uint8_t channel) {
  if (channel > 7) return;              
  Wire.beginTransmission(PCA9548A_ADDR);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

// Probe a channel for an MLX90393, skipping any address already claimed by an
// earlier slot on that same channel.
uint8_t findSensorAddress(uint8_t channel, uint8_t slotIndex) {
  selectMuxChannel(channel);
  delay(10);
  for (uint8_t a = 0; a < NUM_POSSIBLE_ADDRS; a++) {
    uint8_t candidate = MLX_POSSIBLE_ADDRS[a];

    bool taken = false;
    for (uint8_t j = 0; j < slotIndex; j++) {
      if (sensorActive[j] && sensorSlots[j].channel == channel && sensorAddr[j] == candidate) {
        taken = true;
        break;
      }
    }
    if (taken) continue;

    Wire.beginTransmission(candidate);
    if (Wire.endTransmission() == 0) {
      return candidate;
    }
  }
  return 0;
}

void configureSensor(Adafruit_MLX90393 &s) {
  s.setGain(MLX90393_GAIN_2X);
  s.setResolution(MLX90393_X, MLX90393_RES_17);
  s.setResolution(MLX90393_Y, MLX90393_RES_17);
  s.setResolution(MLX90393_Z, MLX90393_RES_17);
  s.setOversampling(MLX90393_OSR_3);
  s.setFilter(MLX90393_FILTER_4);
}

void setup(void) {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(I2C_SDA, I2C_SCL);

  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    sensorActive[i] = false;
    sensorAddr[i]   = 0;
  }

  int firstActive = -1;

  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    uint8_t ch   = sensorSlots[i].channel;
    uint8_t addr = sensorSlots[i].addr;

    if (addr == 0) {
      addr = findSensorAddress(ch, i);
    } else {
      selectMuxChannel(ch);
      delay(10);
      Wire.beginTransmission(addr);
      if (Wire.endTransmission() != 0) addr = 0;
    }

    if (addr == 0) {
      Serial.print("No sensor found for S");
      Serial.print(i);
      Serial.print(" on channel ");
      Serial.println(ch);
      continue;
    }

    selectMuxChannel(ch);
    delay(5);
    if (!sensors[i].begin_I2C(addr, &Wire)) {
      Serial.print("begin_I2C failed for S");
      Serial.println(i);
      continue;
    }
    configureSensor(sensors[i]);

    sensorActive[i] = true;
    sensorAddr[i]   = addr;
    if (firstActive == -1) firstActive = i;

    Serial.print("Found sensor S");
    Serial.print(i);
    Serial.print(" on channel ");
    Serial.print(ch);
    Serial.print(" at address 0x");
    Serial.println(addr, HEX);
  }

  if (firstActive == -1) {
    Serial.println("No sensors detected. Halting.");
    while (1) { delay(10); }
  }
}

void loop(void) {
  for (uint8_t i = 0; i < NUM_SENSORS; i++) {
    if (!sensorActive[i]) {
      Serial.print("S");
      Serial.print(i);
      Serial.println(",ERROR,ERROR,ERROR");
      continue;
    }

    selectMuxChannel(sensorSlots[i].channel);
    delay(2);

    float x, y, z;
    if (sensors[i].readData(&x, &y, &z)) {
      Serial.print("S");
      Serial.print(i);
      Serial.print(",");
      Serial.print(x, 4);
      Serial.print(",");
      Serial.print(y, 4);
      Serial.print(",");
      Serial.println(z, 4);
    } else {
      Serial.print("S");
      Serial.print(i);
      Serial.println(",ERROR,ERROR,ERROR");
    }
  }
  delay(10);
}
