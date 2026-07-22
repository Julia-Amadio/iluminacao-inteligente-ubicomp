import { useCallback, useEffect, useRef, useState } from 'react'
import mqtt, { type MqttClient } from 'mqtt'
import type { LedState } from '../types'

const MQTT_URL = import.meta.env.VITE_MQTT_URL || 'wss://broker.hivemq.com:8884/mqtt'
const CONTROL_TOPIC = import.meta.env.VITE_MQTT_CONTROL_TOPIC || 'pervasiva/grupo1/iluminacao/controle'

export function useMqtt() {
  const clientRef = useRef<MqttClient | null>(null)
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const client = mqtt.connect(MQTT_URL, {
      clientId: `lumen_web_${crypto.randomUUID().slice(0, 8)}`,
      clean: true,
      connectTimeout: 6000,
      reconnectPeriod: 4000,
    })
    clientRef.current = client
    client.on('connect', () => setConnected(true))
    client.on('offline', () => setConnected(false))
    client.on('close', () => setConnected(false))
    client.on('error', () => setConnected(false))
    return () => { client.end(true); clientRef.current = null }
  }, [])

  const publish = useCallback((led: LedState) => new Promise<void>((resolve, reject) => {
    const client = clientRef.current
    if (!client?.connected) return reject(new Error('Broker MQTT desconectado'))
    const payload = JSON.stringify({ led, origem: 'manual' })
    client.publish(CONTROL_TOPIC, payload, { qos: 1, retain: false }, (error) => {
      if (error) reject(error)
      else resolve()
    })
  }), [])

  return { connected, publish }
}
