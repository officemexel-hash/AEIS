"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Smartphone, Trash2 } from "lucide-react";

import {
  bindMobileDevice,
  useOperatorId,
  unbindMobileDevice,
  useOperatorMobileDevices,
} from "../_mobile";

export default function OperatorMobileDevicesPage() {
  const { operatorId } = useOperatorId();
  const { data, refresh } = useOperatorMobileDevices(operatorId);
  const [deviceToken, setDeviceToken] = useState("");
  const [platform, setPlatform] = useState("ios");
  const [deviceLabel, setDeviceLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const devices = data.devices;

  const handleBind = async () => {
    if (!deviceToken.trim()) return;
    setSubmitting(true);
    try {
      await bindMobileDevice({
        operator_id: operatorId,
        device_token: deviceToken.trim(),
        platform,
        device_label: deviceLabel.trim(),
      });
      setDeviceToken("");
      setDeviceLabel("");
      refresh();
    } catch {
      // keep page usable even when routes are not mounted yet
    } finally {
      setSubmitting(false);
    }
  };

  const handleUnbind = async (deviceId: string) => {
    try {
      await unbindMobileDevice(deviceId, operatorId);
      refresh();
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Powiązane urządzenia</h1>
        <p className="text-sm text-muted-foreground">
          Device registry for <span className="font-mono text-foreground">{operatorId}</span>
        </p>
      </div>

      <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Bind New Device</p>
        <div className="mt-4 grid gap-3 md:grid-cols-[1.2fr_0.7fr_1fr_auto]">
          <input
            value={deviceToken}
            onChange={(event) => setDeviceToken(event.target.value)}
            className="h-10 rounded-lg border border-border/40 bg-background/40 px-3 text-sm outline-none transition focus:border-sylion-blue/40"
            placeholder="device token"
          />
          <select
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
            className="h-10 rounded-lg border border-border/40 bg-background/40 px-3 text-sm outline-none transition focus:border-sylion-blue/40"
          >
            <option value="ios">iOS</option>
            <option value="android">Android</option>
            <option value="web">Web</option>
          </select>
          <input
            value={deviceLabel}
            onChange={(event) => setDeviceLabel(event.target.value)}
            className="h-10 rounded-lg border border-border/40 bg-background/40 px-3 text-sm outline-none transition focus:border-sylion-blue/40"
            placeholder="device label"
          />
          <Button onClick={handleBind} disabled={submitting}>
            Bind
          </Button>
        </div>
      </Card>

      <div className="grid gap-4">
        {devices.map((device) => (
          <Card key={device.device_id} className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sylion-blue/10">
                  <Smartphone className="h-5 w-5 text-sylion-blue" />
                </div>
                <div>
                  <p className="text-sm font-medium">{device.device_label || device.device_token}</p>
                  <p className="text-xs font-mono text-muted-foreground">{device.device_token}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Badge variant="outline" className="border-sylion-blue/30 text-sylion-blue">
                  {device.platform}
                </Badge>
                <Badge variant="outline" className="border-sylion-green/30 text-sylion-green">
                  ACTIVE
                </Badge>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-sylion-red/30 text-sylion-red hover:bg-sylion-red/10"
                  onClick={() => handleUnbind(device.device_id)}
                >
                  <Trash2 className="mr-1 h-3.5 w-3.5" />
                  Unbind
                </Button>
              </div>
            </div>
          </Card>
        ))}

        {devices.length === 0 && (
          <Card className="border-[rgba(148,163,184,0.08)] bg-[#0f1629] p-8 text-center">
            <p className="text-sm text-muted-foreground">Brak powiązanych urządzeń.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
