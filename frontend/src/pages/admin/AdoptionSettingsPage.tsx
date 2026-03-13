import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ClockIcon, ArrowPathIcon, KeyIcon } from '@heroicons/react/24/outline';
import Layout from '../../components/layout/Layout';
import { AXIOS_INSTANCE } from '../../services/api-client';
import {
  Button,
  Label,
  Alert,
  Spinner,
  DatePicker,
  Switch,
  Badge,
  Select,
  SelectOption,
  Page,
  PageHeader,
  PageBody,
  Panel,
  PanelHeader,
  PanelTitle,
  PanelDescription,
  PanelBody,
  SectionHeader,
} from '../../components/ui';
import { useAuth } from '../../stores/useAuth';
import { useToasts } from '../../stores/useToasts';
import { AdoptionAccessPage } from './AdoptionAccessPage';

interface AdoptionSettingsResponse {
  customer_id: string;
  initial_sync_start_date: string;
  schedule_enabled: boolean;
  schedule_cron: string | null;
  last_synced_at: string | null;
  sync_health: 'healthy' | 'degraded' | 'unknown';
  adoption_provider_configured: boolean;
  compliance_api_key_configured: boolean;
  compliance_status: 'success' | 'failed' | 'untested' | null;
}

const DAYS_OF_WEEK = [
  { key: 'sun', label: 'S', fullLabel: 'Sunday', cronValue: 0 },
  { key: 'mon', label: 'M', fullLabel: 'Monday', cronValue: 1 },
  { key: 'tue', label: 'T', fullLabel: 'Tuesday', cronValue: 2 },
  { key: 'wed', label: 'W', fullLabel: 'Wednesday', cronValue: 3 },
  { key: 'thu', label: 'T', fullLabel: 'Thursday', cronValue: 4 },
  { key: 'fri', label: 'F', fullLabel: 'Friday', cronValue: 5 },
  { key: 'sat', label: 'S', fullLabel: 'Saturday', cronValue: 6 },
];

function timeToCron(time: string, selectedDays: string[]): string {
  const [hours, minutes] = time.split(':').map(Number);
  const utcHours = (hours + 5) % 24;

  if (selectedDays.length === 0 || selectedDays.length === 7) {
    return `${minutes} ${utcHours} * * *`;
  }

  const cronDays = selectedDays
    .map((dayKey) => DAYS_OF_WEEK.find((d) => d.key === dayKey)?.cronValue)
    .filter((v): v is number => v !== undefined)
    .sort((a, b) => a - b)
    .join(',');

  return `${minutes} ${utcHours} * * ${cronDays}`;
}

function cronToTimeAndDays(cron: string): { time: string; selectedDays: string[] } {
  const parts = cron.split(' ');
  if (parts.length !== 5) return { time: '06:00', selectedDays: DAYS_OF_WEEK.map((d) => d.key) };

  const [minute, hour, , , dayOfWeek] = parts;
  const easternHour = (parseInt(hour, 10) - 5 + 24) % 24;
  const time = `${easternHour.toString().padStart(2, '0')}:${minute.padStart(2, '0')}`;

  let selectedDays: string[] = [];
  if (dayOfWeek === '*' || dayOfWeek === '0-6' || dayOfWeek === '0,1,2,3,4,5,6') {
    selectedDays = DAYS_OF_WEEK.map((d) => d.key);
  } else if (dayOfWeek === '1-5') {
    selectedDays = ['mon', 'tue', 'wed', 'thu', 'fri'];
  } else {
    const dayNumbers = dayOfWeek.split(',').map((d) => parseInt(d.trim(), 10));
    selectedDays = dayNumbers
      .map((num) => DAYS_OF_WEEK.find((d) => d.cronValue === num)?.key)
      .filter(Boolean) as string[];
  }

  return { time, selectedDays };
}

function formatTimeDisplay(time: string): string {
  const [hours, minutes] = time.split(':').map(Number);
  const period = hours >= 12 ? 'PM' : 'AM';
  const displayHours = hours % 12 || 12;
  return `${displayHours}:${minutes.toString().padStart(2, '0')} ${period}`;
}

function parseRunTimeToParts(time: string): { hour12: string; minute: string; period: 'AM' | 'PM' } {
  const [hours24Raw, minuteRaw] = time.split(':');
  const hours24 = Number.parseInt(hours24Raw ?? '6', 10);
  const minute = (minuteRaw ?? '00').padStart(2, '0');
  const period: 'AM' | 'PM' = hours24 >= 12 ? 'PM' : 'AM';
  const hour12 = String(hours24 % 12 || 12);
  return { hour12, minute, period };
}

function buildRunTimeFromParts(hour12: string, minute: string, period: 'AM' | 'PM'): string {
  const parsedHour12 = Number.parseInt(hour12, 10);
  let hours24 = parsedHour12 % 12;
  if (period === 'PM') {
    hours24 += 12;
  }
  return `${String(hours24).padStart(2, '0')}:${minute.padStart(2, '0')}`;
}

export default function AdoptionSettingsPage() {
  const queryClient = useQueryClient();
  const { push: addToast } = useToasts();
  const isPlatformAdmin = useAuth((state) => state.isPlatformAdmin());
  const canManageJobs = useAuth((state) => state.hasPermission('adoption:manage_jobs')) || isPlatformAdmin;

  const { data, isLoading, error } = useQuery({
    queryKey: ['adoption-settings'],
    queryFn: async () => {
      const response = await AXIOS_INSTANCE.get<AdoptionSettingsResponse>('/api/v1/admin/adoption-settings');
      return response.data;
    },
  });

  const [startDate, setStartDate] = useState('');
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleCron, setScheduleCron] = useState('');
  const [selectedDays, setSelectedDays] = useState<string[]>(DAYS_OF_WEEK.map((d) => d.key));
  const [runTime, setRunTime] = useState('06:00');
  const [timeHour, setTimeHour] = useState('6');
  const [timeMinute, setTimeMinute] = useState('00');
  const [timePeriod, setTimePeriod] = useState<'AM' | 'PM'>('AM');

  const startDateValue = useMemo(() => {
    if (!startDate) return null;
    const parsed = new Date(`${startDate}T00:00:00`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }, [startDate]);

  React.useEffect(() => {
    if (data) {
      setStartDate(data.initial_sync_start_date || '');
      setScheduleEnabled(data.schedule_enabled);
      const cronValue = data.schedule_cron || '';
      setScheduleCron(cronValue);
      if (cronValue) {
        const parsed = cronToTimeAndDays(cronValue);
        setRunTime(parsed.time);
        setSelectedDays(parsed.selectedDays);
        const timeParts = parseRunTimeToParts(parsed.time);
        setTimeHour(timeParts.hour12);
        setTimeMinute(timeParts.minute);
        setTimePeriod(timeParts.period);
      }
    }
  }, [data]);

  React.useEffect(() => {
    if (!scheduleEnabled) {
      setScheduleCron('');
      return;
    }
    setScheduleCron(timeToCron(runTime, selectedDays));
  }, [runTime, selectedDays, scheduleEnabled]);

  React.useEffect(() => {
    setRunTime(buildRunTimeFromParts(timeHour, timeMinute, timePeriod));
  }, [timeHour, timeMinute, timePeriod]);

  const saveSettings = useMutation({
    mutationFn: async () => {
      const payload: Partial<AdoptionSettingsResponse> = {
        initial_sync_start_date: startDate,
        schedule_enabled: scheduleEnabled,
        schedule_cron: scheduleEnabled ? (scheduleCron || null) : null,
      };
      const response = await AXIOS_INSTANCE.put('/api/v1/admin/adoption-settings', payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adoption-settings'] });
      addToast({ kind: 'success', message: 'Adoption settings saved' });
    },
    onError: (err: any) => {
      addToast({
        kind: 'error',
        message: err?.response?.data?.detail || 'Failed to save adoption settings',
      });
    },
  });

  const healthLabel = useMemo(() => {
    if (!data) return 'Unknown';
    if (data.sync_health === 'healthy') return 'Healthy';
    if (data.sync_health === 'degraded') return 'Needs Recovery';
    return 'Unknown';
  }, [data]);
  const healthNote = useMemo(() => {
    if (data?.sync_health === 'degraded')
      return 'OpenAI Compliance API data may be delayed by 1–2 days. Daily metrics will catch up on the next sync.';
    return null;
  }, [data]);
  const complianceReady = Boolean(data?.compliance_api_key_configured);
  const providerReady = Boolean(data?.adoption_provider_configured);

  const toggleDay = (dayKey: string) => {
    setSelectedDays((prev) => (prev.includes(dayKey) ? prev.filter((d) => d !== dayKey) : [...prev, dayKey]));
  };

  const selectAllDays = () => setSelectedDays(DAYS_OF_WEEK.map((d) => d.key));
  const selectWeekdays = () => setSelectedDays(['mon', 'tue', 'wed', 'thu', 'fri']);
  const selectWeekends = () => setSelectedDays(['sat', 'sun']);

  return (
    <Layout>
      <Page maxWidth="xl">
        <PageHeader
          title="Adoption Settings"
          description="Configure sync setup, scheduling, and access sharing in one place."
          actions={canManageJobs ? (
            <Link to="/admin/jobs">
              <Button variant="secondary">
                <ClockIcon className="h-4 w-4" />
                Open Job Scheduler
              </Button>
            </Link>
          ) : undefined}
        />
        <PageBody className="space-y-8">
          {error && <Alert variant="error">Failed to load adoption settings.</Alert>}

          <Panel>
            <PanelHeader>
              <PanelTitle>Step 1: OpenAI Compliance Setup</PanelTitle>
              <PanelDescription className="text-xs">
                Configure an OpenAI key and workspace with Compliance API access before running adoption sync.
              </PanelDescription>
            </PanelHeader>
            <PanelBody>
              {isLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Spinner />
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-4 rounded-lg border border-gray-200 dark:border-dark-border p-4">
                    <div className="flex items-start gap-3">
                      <div className="rounded-lg bg-eliza-red/10 p-2">
                        <KeyIcon className="h-5 w-5 text-eliza-red" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-charcoal dark:text-gray-100">OpenAI Compliance API</p>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          Required for ChatGPT Enterprise adoption sync. Set an adoption source OpenAI provider and workspace.
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <Badge variant={providerReady ? 'success' : 'warning'}>
                            {providerReady ? 'Provider Selected' : 'Provider Not Configured'}
                          </Badge>
                          <Badge variant={complianceReady ? 'success' : 'warning'}>
                            {complianceReady ? 'Compliance Key Configured' : 'Compliance Key Missing'}
                          </Badge>
                          {data?.compliance_status && (
                            <Badge variant={data.compliance_status === 'success' ? 'success' : data.compliance_status === 'failed' ? 'danger' : 'secondary'}>
                              Compliance Test: {data.compliance_status}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <Link to="/admin/settings">
                      <Button variant="outline">Open AI Providers</Button>
                    </Link>
                  </div>
                </div>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Step 2: Sync Schedule + Backfill Window</PanelTitle>
              <PanelDescription className="text-xs">Set initial data range and recurring sync cadence.</PanelDescription>
            </PanelHeader>
            <PanelBody>
              {isLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Spinner />
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="mb-2 block">Initial Data Sync Start Date</Label>
                      <DatePicker
                        value={startDateValue}
                        onChange={(date) => setStartDate(date ? date.toISOString().slice(0, 10) : '')}
                        maxDate={new Date()}
                        placeholder="Choose first date to sync data from"
                        className="w-full"
                      />
                      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                        This is the earliest data date to pull into Adoption metrics. It does not control when the scheduled job starts running.
                      </p>
                    </div>
                    <div>
                      <Label className="mb-2 block">Run at (Eastern Time)</Label>
                      <div className="grid grid-cols-3 gap-2 max-w-md">
                        <Select value={timeHour} onValueChange={setTimeHour}>
                          <SelectOption value="1">01</SelectOption>
                          <SelectOption value="2">02</SelectOption>
                          <SelectOption value="3">03</SelectOption>
                          <SelectOption value="4">04</SelectOption>
                          <SelectOption value="5">05</SelectOption>
                          <SelectOption value="6">06</SelectOption>
                          <SelectOption value="7">07</SelectOption>
                          <SelectOption value="8">08</SelectOption>
                          <SelectOption value="9">09</SelectOption>
                          <SelectOption value="10">10</SelectOption>
                          <SelectOption value="11">11</SelectOption>
                          <SelectOption value="12">12</SelectOption>
                        </Select>
                        <Select value={timeMinute} onValueChange={setTimeMinute}>
                          <SelectOption value="00">00</SelectOption>
                          <SelectOption value="05">05</SelectOption>
                          <SelectOption value="10">10</SelectOption>
                          <SelectOption value="15">15</SelectOption>
                          <SelectOption value="20">20</SelectOption>
                          <SelectOption value="25">25</SelectOption>
                          <SelectOption value="30">30</SelectOption>
                          <SelectOption value="35">35</SelectOption>
                          <SelectOption value="40">40</SelectOption>
                          <SelectOption value="45">45</SelectOption>
                          <SelectOption value="50">50</SelectOption>
                          <SelectOption value="55">55</SelectOption>
                        </Select>
                        <Select value={timePeriod} onValueChange={(value) => setTimePeriod(value as 'AM' | 'PM')}>
                          <SelectOption value="AM">AM</SelectOption>
                          <SelectOption value="PM">PM</SelectOption>
                        </Select>
                      </div>
                      <div className="mt-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {formatTimeDisplay(runTime)} ET
                        </span>
                      </div>
                    </div>
                  </div>

                  <div>
                    <SectionHeader
                      title="Schedule Cron (optional)"
                      description="Choose the days and time for the automatic sync schedule."
                      className="mb-3"
                    />

                    <div className="flex flex-wrap items-center gap-1.5 mb-3">
                      {DAYS_OF_WEEK.map((day) => (
                        <Button
                          key={day.key}
                          type="button"
                          variant={selectedDays.includes(day.key) ? 'brand' : 'secondary'}
                          size="sm"
                          onClick={() => toggleDay(day.key)}
                          title={day.fullLabel}
                          className="w-9 h-9 rounded-full p-0"
                        >
                          {day.label}
                        </Button>
                      ))}
                    </div>

                    <div className="flex gap-2 flex-wrap">
                      <Button type="button" variant="outline" size="sm" onClick={selectAllDays}>
                        Every day
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={selectWeekdays}>
                        Weekdays
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={selectWeekends}>
                        Weekends
                      </Button>
                    </div>

                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                      {selectedDays.length === 0 && 'No days selected - will run every day'}
                      {selectedDays.length === 7 && 'Runs every day'}
                      {selectedDays.length > 0 && selectedDays.length < 7 && (
                        <>Runs on {selectedDays.map((key) => DAYS_OF_WEEK.find((d) => d.key === key)?.fullLabel).join(', ')}</>
                      )}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Cron expression: <span className="font-mono">{scheduleCron || 'Not set'}</span>
                    </p>
                  </div>

                  <div className="flex items-center justify-between rounded-lg border border-gray-200 dark:border-dark-border px-3 py-2">
                    <Label className="text-sm font-normal text-charcoal dark:text-gray-100">Enable scheduled sync</Label>
                    <Switch
                      checked={scheduleEnabled}
                      onCheckedChange={setScheduleEnabled}
                      aria-label="Enable scheduled sync"
                    />
                  </div>

                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>
                        Last synced:{' '}
                        <strong className="text-charcoal dark:text-gray-100">
                          {data?.last_synced_at ? new Date(data.last_synced_at).toLocaleString() : 'Never'}
                        </strong>
                      </span>
                      <span className="inline-flex items-center gap-2">
                        Sync health:
                        <Badge variant={data?.sync_health === 'healthy' ? 'success' : data?.sync_health === 'degraded' ? 'warning' : 'secondary'}>
                          {healthLabel}
                        </Badge>
                      </span>
                    </div>
                    {healthNote && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">{healthNote}</p>
                    )}
                  </div>

                  <div className="pt-2">
                    <Button onClick={() => saveSettings.mutate()} disabled={saveSettings.isPending}>
                      {saveSettings.isPending ? (
                        <>
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        'Save Settings'
                      )}
                    </Button>
                  </div>
                </div>
              )}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Step 3: Adoption Data Sharing</PanelTitle>
              <PanelDescription className="text-xs">
                Control which tenants can view adoption metrics across your sharing relationships.
              </PanelDescription>
            </PanelHeader>
            <PanelBody className="pt-2">
              <AdoptionAccessPage embedded showHeader={false} />
            </PanelBody>
          </Panel>
        </PageBody>
      </Page>
    </Layout>
  );
}
