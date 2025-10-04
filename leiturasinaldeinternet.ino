#include <Arduino.h>
#include "FS.h"
#include "SD.h"
#include "SPI.h"

#define CS_PIN 5

#define UART_RX2 17
#define UART_TX2 16

typedef struct __data_payload_t
{
    char data[512];
    size_t size;

} data_payload_t;

QueueHandle_t queueSerialNordianRx = NULL;
SemaphoreHandle_t sdCardMutex = NULL;

TaskHandle_t nordianRxTask = NULL;
TaskHandle_t sdCardTxTask = NULL;
TaskHandle_t modemCommandTxTask = NULL;

bool is_file_name = false;
volatile bool sd_can_write = true;

// Task que lê da Serial2 e manda para fila
void serialNordianRx(void *arg) {
  data_payload_t serial_data_rx = {0};
  size_t current_index = 0;

  while (true) {
    while (Serial2.available()) {
      char serial_byte = Serial2.read();

      serial_data_rx.data[current_index++] = serial_byte;

      if (serial_byte == '\n' || current_index >= sizeof(serial_data_rx.data) - 1) {
        serial_data_rx.data[current_index] = '\0';
        serial_data_rx.size = current_index;

        if(xQueueSend(queueSerialNordianRx, &serial_data_rx, pdMS_TO_TICKS(100)) == pdFAIL) {
          xQueueReset(queueSerialNordianRx);
          vTaskDelay(pdMS_TO_TICKS(100));
          if(xQueueSend(queueSerialNordianRx, &serial_data_rx, pdMS_TO_TICKS(100)) == pdFAIL) {
            Serial.println("Error enqueue queueSerialNordianRx");
          }
        }

        serial_data_rx = {0};
        current_index = 0;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// Task que grava os dados do modem no cartão SD
void sdCardTx(void *arg) {
  data_payload_t nordian_serial_data_tx = {0};
  const char *path_file_name = "/rfsts_log.txt";

  while (true) {
    if(xQueueReceive(queueSerialNordianRx, &nordian_serial_data_tx, pdMS_TO_TICKS(10)) == pdPASS) {

      if (sd_can_write) {
        xSemaphoreTake(sdCardMutex, portMAX_DELAY);

        File file = SD.open(path_file_name, FILE_APPEND);

        if (!file) {
          Serial.println("[SD] Falha ao abrir arquivo");
          xSemaphoreGive(sdCardMutex);
          break;
        }

        if (file.write((uint8_t*)nordian_serial_data_tx.data, nordian_serial_data_tx.size) > 0) {
          Serial.println("[SD] Gravou no arquivo");
        } else {
          Serial.println("[SD] Falha ao gravar");
        }

        file.close();

        xSemaphoreGive(sdCardMutex);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// Task que envia a APN uma vez e depois envia AT#RFSTS a cada 15s
void modemCommandTx(void *arg) {
  const TickType_t delay15s = pdMS_TO_TICKS(15000);

  Serial.println("[MODEM] Enviando configuração de APN...");
  Serial2.println("AT+CGDCONT=1,\"IP\",\"zap.vivo.com.br\"");
  vTaskDelay(pdMS_TO_TICKS(3000));  // espera a resposta

  while (true) {
    Serial.println("[MODEM] Enviando AT#RFSTS...");
    Serial2.println("AT#RFSTS");
    vTaskDelay(delay15s);
  }
}

void setup() {
  Serial.begin(115200);

  Serial2.setRxBufferSize(4096);
  Serial2.begin(115200, SERIAL_8N1, UART_RX2, UART_TX2);

  queueSerialNordianRx = xQueueCreate(8, sizeof(data_payload_t));
  sdCardMutex = xSemaphoreCreateMutex();

  // Inicializa cartão SD
  while (!SD.begin(CS_PIN)) {
    Serial.println("[SD] Falha na inicialização do cartão SD!");
    delay(2000);
  }
  Serial.println("[SD] Cartão SD inicializado com sucesso.");

  // Cria tasks FreeRTOS
  xTaskCreatePinnedToCore(serialNordianRx, "serial_nordian_rx", 10240, NULL, 6, &nordianRxTask, APP_CPU_NUM);
  xTaskCreatePinnedToCore(sdCardTx, "sd_card_tx", 10240, NULL, 5, &sdCardTxTask, APP_CPU_NUM);
  xTaskCreatePinnedToCore(modemCommandTx, "modem_command_tx", 4096, NULL, 4, &modemCommandTxTask, APP_CPU_NUM);
}

void loop() {
  // Não usa nada no loop, as tasks fazem o trabalho
  vTaskDelay(portMAX_DELAY);
}
 