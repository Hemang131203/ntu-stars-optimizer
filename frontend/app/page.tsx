"use client";

import { useRef, useState } from "react";

type ClassSession = {
  course: string;
  course_name: string;
  index: string;
  type: string;
  group: string;
  day: string;
  start: string;
  end: string;
  venue: string;
  remark: string;
};

type Timetable = {
  selected_indexes: Record<string, string>;
  classes: ClassSession[];
  score: number;
  score_breakdown: Record<string, number>;
  explanations: string[];
};

type ApiResponse = {
  detected_courses: {
    course: string;
    course_name: string;
    indexes_found: number;
  }[];
  total_rows_extracted: number;
  estimated_combinations: number;
  valid_timetables_found: number;
  top_timetables: Timetable[];
  message: string;
  search_truncated?: boolean;
  truncation_reason?: string | null;
  optimization_elapsed_seconds?: number;
};

type AvoidTimeWindow = {
  day: string;
  start: string;
  end: string;
};

const days = ["MON", "TUE", "WED", "THU", "FRI"];

const dayOrder: Record<string, number> = {
  MON: 1,
  TUE: 2,
  WED: 3,
  THU: 4,
  FRI: 5,
  SAT: 6,
  SUN: 7,
};

function groupClassesByDay(classes: ClassSession[]) {
  const sorted = [...classes].sort((a, b) => {
    const dayDiff = (dayOrder[a.day] ?? 99) - (dayOrder[b.day] ?? 99);

    if (dayDiff !== 0) return dayDiff;

    return a.start.localeCompare(b.start);
  });

  return sorted.reduce<Record<string, ClassSession[]>>((acc, session) => {
    if (!acc[session.day]) {
      acc[session.day] = [];
    }

    acc[session.day].push(session);
    return acc;
  }, {});
}

function formatPreferenceTime(time: string) {
  if (!time) return "not set";
  return time;
}

async function extractErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const payload = await response.json();

      if (typeof payload.detail === "string") {
        return payload.detail;
      }

      if (typeof payload.message === "string") {
        return payload.message;
      }
    } catch {
      // Ignore parse errors and fall through.
    }
  }

  try {
    const text = await response.text();
    if (text.trim()) {
      return text;
    }
  } catch {
    // Ignore read errors and use fallback.
  }

  return "Failed to generate timetable.";
}

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [avoidBeforeTime, setAvoidBeforeTime] = useState("09:00");
  const [avoidAfterTime, setAvoidAfterTime] = useState("17:00");
  const [avoidDays, setAvoidDays] = useState<string[]>([]);
  const [preferFewerSchoolDays, setPreferFewerSchoolDays] = useState(false);
  const [preferShorterGaps, setPreferShorterGaps] = useState(false);
  const [minimumGapMinutes, setMinimumGapMinutes] = useState(10);
  const [avoidTimeWindows, setAvoidTimeWindows] = useState<AvoidTimeWindow[]>([
    {
      day: "THU",
      start: "08:30",
      end: "11:00",
    },
  ]);

  const [result, setResult] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function buildPreferences() {
    return {
      avoid_before_time: avoidBeforeTime || null,
      avoid_after_time: avoidAfterTime || null,
      avoid_days: avoidDays,
      prefer_fewer_school_days: preferFewerSchoolDays,
      prefer_shorter_gaps: preferShorterGaps,
      minimum_gap_minutes: minimumGapMinutes,
      avoid_time_windows: avoidTimeWindows.filter(
        (window) => window.day && window.start && window.end
      ),
    };
  }

  function toggleAvoidDay(day: string) {
    setAvoidDays((current) => {
      if (current.includes(day)) {
        return current.filter((d) => d !== day);
      }

      return [...current, day];
    });
  }

  function updateAvoidWindow(
    index: number,
    field: keyof AvoidTimeWindow,
    value: string
  ) {
    setAvoidTimeWindows((current) =>
      current.map((window, i) =>
        i === index
          ? {
              ...window,
              [field]: value,
            }
          : window
      )
    );
  }

  function addAvoidWindow() {
    setAvoidTimeWindows((current) => [
      ...current,
      {
        day: "MON",
        start: "12:30",
        end: "14:00",
      },
    ]);
  }

  function removeAvoidWindow(index: number) {
    setAvoidTimeWindows((current) => current.filter((_, i) => i !== index));
  }

  async function handleGenerate() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const selectedFiles = Array.from(fileInputRef.current?.files ?? []);

      if (selectedFiles.length === 0) {
        throw new Error("Please upload at least one PDF.");
      }

      const preferences = buildPreferences();

      const formData = new FormData();

      selectedFiles.forEach((file) => {
        formData.append("files", file);
      });

      formData.append("preferences_json", JSON.stringify(preferences));

      const apiUrl = process.env.NEXT_PUBLIC_API_URL;

      if (!apiUrl) {
        throw new Error("API URL is not configured.");
      }

      const response = await fetch(`${apiUrl}/optimize`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await extractErrorMessage(response));
      }

      const data: ApiResponse = await response.json();
      setResult(data);
    } catch (err) {
      if (err instanceof TypeError && err.message.includes("Failed to fetch")) {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL;
        setError(
          `Cannot reach backend API (${apiUrl || "URL not configured"}). ` +
            "The Render service may be sleeping, unavailable, or the request timed out."
        );
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setLoading(false);
    }
  }

  const timeInputClass =
    "mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-100 outline-none focus:border-cyan-400 [color-scheme:dark] [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-100 [&::-webkit-calendar-picker-indicator]:brightness-0 [&::-webkit-calendar-picker-indicator]:invert";

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-10">
        <header className="mb-10">
          <p className="text-sm font-medium text-cyan-300">NTU STARS Helper</p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">
            Timetable Optimizer
          </h1>
          <p className="mt-3 max-w-3xl text-slate-300">
            Upload one class schedule PDF per module. The app extracts all
            available indexes, removes clashing combinations, and ranks the best
            timetables based on your preferences.
          </p>
          <p className="mt-2 text-sm text-slate-500">
            Note: Generated timetables are suggestions based on extracted data. This tool does not have real-time access to STARS and cannot register timetables in the STARS system. It is only a planning helper to visualize possible timetable combinations and their preference matches. Always verify against the official STARS system before making decisions.
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
            <h2 className="text-xl font-semibold">1. Upload PDFs</h2>
            <p className="mt-2 text-sm text-slate-400">
              Select one class schedule PDF per module. Upload all files at once.
            </p>

            <input
              ref={fileInputRef}
              className="mt-5 block w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-400 file:px-4 file:py-2 file:font-semibold file:text-slate-950 hover:file:bg-cyan-300"
              type="file"
              accept="application/pdf"
              multiple
              onChange={(event) => {
                setFiles(Array.from(event.target.files ?? []));
              }}
            />

            {files.length > 0 && (
              <div className="mt-5 rounded-xl bg-slate-950 p-4">
                <p className="mb-2 text-sm font-semibold text-slate-300">
                  Selected files:
                </p>
                <ul className="space-y-1 text-sm text-slate-400">
                  {files.map((file) => (
                    <li key={file.name}>• {file.name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg">
            <h2 className="text-xl font-semibold">2. Preferences</h2>
            <p className="mt-2 text-sm text-slate-400">
              Preferences apply to tutorials, labs, and other selectable classes.
              Lectures are still checked for clashes but ignored for preference
              scoring.
            </p>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-slate-300">
                  Avoid tut/lab before
                </span>
                <input
                  type="time"
                  value={avoidBeforeTime}
                  onChange={(event) => setAvoidBeforeTime(event.target.value)}
                  className={timeInputClass}
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">
                  Avoid tut/lab after
                </span>
                <input
                  type="time"
                  value={avoidAfterTime}
                  onChange={(event) => setAvoidAfterTime(event.target.value)}
                  className={timeInputClass}
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-slate-300">
                  Minimum preferred gap, minutes
                </span>
                <input
                  type="number"
                  min={0}
                  max={600}
                  value={minimumGapMinutes}
                  onChange={(event) =>
                    setMinimumGapMinutes(Number(event.target.value))
                  }
                  className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 text-slate-100 outline-none focus:border-cyan-400"
                />
              </label>

              <div className="flex flex-col justify-end gap-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
                <label className="flex items-center gap-3 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={preferFewerSchoolDays}
                    onChange={(event) =>
                      setPreferFewerSchoolDays(event.target.checked)
                    }
                    className="h-4 w-4 accent-cyan-400"
                  />
                  Prefer fewer school days
                </label>

                <label className="flex items-center gap-3 text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={preferShorterGaps}
                    onChange={(event) =>
                      setPreferShorterGaps(event.target.checked)
                    }
                    className="h-4 w-4 accent-cyan-400"
                  />
                  Prefer shorter gaps
                </label>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950 p-4">
              <p className="text-sm font-semibold text-slate-300">
                Avoid tut/lab on selected days
              </p>

              <div className="mt-3 flex flex-wrap gap-2">
                {days.map((day) => (
                  <button
                    key={day}
                    type="button"
                    onClick={() => toggleAvoidDay(day)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                      avoidDays.includes(day)
                        ? "bg-cyan-400 text-slate-950"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {day}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-300">
                    Custom avoid time windows
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Example: avoid tutorials/labs on MON from 12:30 to 14:00.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={addAvoidWindow}
                  className="rounded-lg bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300"
                >
                  + Add
                </button>
              </div>

              <div className="mt-4 space-y-3">
                {avoidTimeWindows.map((window, index) => (
                  <div
                    key={index}
                    className="grid gap-3 rounded-xl bg-slate-900 p-3 md:grid-cols-[1fr_1fr_1fr_auto]"
                  >
                    <select
                      value={window.day}
                      onChange={(event) =>
                        updateAvoidWindow(index, "day", event.target.value)
                      }
                      className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-slate-100 outline-none focus:border-cyan-400"
                    >
                      {days.map((day) => (
                        <option key={day} value={day}>
                          {day}
                        </option>
                      ))}
                    </select>

                    <input
                      type="time"
                      value={window.start}
                      onChange={(event) =>
                        updateAvoidWindow(index, "start", event.target.value)
                      }
                      className={timeInputClass.replace("mt-2 ", "")}
                    />

                    <input
                      type="time"
                      value={window.end}
                      onChange={(event) =>
                        updateAvoidWindow(index, "end", event.target.value)
                      }
                      className={timeInputClass.replace("mt-2 ", "")}
                    />

                    <button
                      type="button"
                      onClick={() => removeAvoidWindow(index)}
                      className="rounded-lg bg-red-400/10 px-3 py-2 text-sm font-semibold text-red-300 hover:bg-red-400/20"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-cyan-400/20 bg-cyan-400/10 p-4">
              <p className="text-sm font-semibold text-cyan-200">
                Preferences Preview
              </p>

              <div className="mt-3 space-y-2 text-sm text-slate-300">
                <p>
                  • Avoid tutorials/labs before{" "}
                  <span className="font-semibold text-slate-100">
                    {formatPreferenceTime(avoidBeforeTime)}
                  </span>
                </p>

                <p>
                  • Avoid tutorials/labs after{" "}
                  <span className="font-semibold text-slate-100">
                    {formatPreferenceTime(avoidAfterTime)}
                  </span>
                </p>

                <p>
                  • Avoid tutorials/labs on{" "}
                  <span className="font-semibold text-slate-100">
                    {avoidDays.length > 0 ? avoidDays.join(", ") : "no days"}
                  </span>
                </p>

                <p>
                  • Minimum preferred gap:{" "}
                  <span className="font-semibold text-slate-100">
                    {minimumGapMinutes} minutes
                  </span>
                </p>

                <p>
                  • Prefer fewer school days:{" "}
                  <span className="font-semibold text-slate-100">
                    {preferFewerSchoolDays ? "Yes" : "No"}
                  </span>
                </p>

                <p>
                  • Prefer shorter gaps:{" "}
                  <span className="font-semibold text-slate-100">
                    {preferShorterGaps ? "Yes" : "No"}
                  </span>
                </p>

                <div>
                  <p>• Custom avoid windows:</p>

                  {avoidTimeWindows.length > 0 ? (
                    <ul className="mt-1 ml-5 list-disc space-y-1 text-slate-400">
                      {avoidTimeWindows.map((window, index) => (
                        <li key={index}>
                          {window.day} {window.start}–{window.end}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="ml-5 text-slate-400">None</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
          <button
            onClick={handleGenerate}
            className="rounded-xl bg-cyan-400 px-6 py-3 font-semibold text-slate-950 shadow-lg transition hover:bg-cyan-300"
          >
            {loading ? "Generating..." : "Generate Timetable"}
          </button>

          {error && (
            <pre className="max-w-3xl whitespace-pre-wrap rounded-xl bg-red-950 p-4 text-sm text-red-200">
              {error}
            </pre>
          )}
        </div>

        {loading && (
          <div className="mt-6 rounded-2xl border border-cyan-400/30 bg-cyan-400/10 p-4 text-cyan-100">
            Generating timetable... This may take a few seconds.
          </div>
        )}

        {result && (
          <section className="mt-10 space-y-6">
            <div
              className={`rounded-2xl border p-4 ${
                result.search_truncated
                  ? "border-amber-500/40 bg-amber-500/10 text-amber-100"
                  : "border-cyan-400/30 bg-cyan-400/10 text-cyan-100"
              }`}
            >
              {result.message}
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="text-2xl font-bold">Results Summary</h2>

              <div className="mt-4 grid gap-4 md:grid-cols-5">
                <div className="rounded-xl bg-slate-950 p-4">
                  <p className="text-sm text-slate-400">Rows extracted</p>
                  <p className="mt-1 text-2xl font-bold">
                    {result.total_rows_extracted}
                  </p>
                </div>

                

                <div className="rounded-xl bg-slate-950 p-4">
                  <p className="text-sm text-slate-400">
                    Clash-free timetables
                  </p>
                  <p className="mt-1 text-2xl font-bold">
                    {result.valid_timetables_found}
                  </p>
                </div>

                <div className="rounded-xl bg-slate-950 p-4">
                  <p className="text-sm text-slate-400">Modules detected</p>
                  <p className="mt-1 text-2xl font-bold">
                    {result.detected_courses.length}
                  </p>
                </div>

                
              </div>

              <div className="mt-5">
                <h3 className="font-semibold">Detected courses</h3>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {result.detected_courses.map((course) => (
                    <div
                      key={course.course}
                      className="rounded-xl border border-slate-800 bg-slate-950 p-4"
                    >
                      <p className="font-semibold text-cyan-300">
                        {course.course}
                      </p>
                      <p className="text-sm text-slate-300">
                        {course.course_name}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {course.indexes_found} indexes found
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <h2 className="text-2xl font-bold">Top Recommended Timetables</h2>

            {result.top_timetables.map((timetable, index) => {
              const classesByDay = groupClassesByDay(timetable.classes);

              return (
                <div
                  key={index}
                  className="rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-lg"
                >
                  <div>
                    <h3 className="text-xl font-bold">
                      Rank {index + 1}{" "}
                    </h3>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {Object.entries(timetable.selected_indexes).map(
                        ([course, courseIndex]) => (
                          <span
                            key={course}
                            className="rounded-full bg-cyan-400/10 px-3 py-1 text-sm text-cyan-200"
                          >
                            {course}: {courseIndex}
                          </span>
                        )
                      )}
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 lg:grid-cols-5">
                    {Object.entries(classesByDay).map(([day, sessions]) => (
                      <div
                        key={day}
                        className="rounded-xl border border-slate-800 bg-slate-950 p-4"
                      >
                        <h4 className="font-bold text-cyan-300">{day}</h4>

                        <div className="mt-3 space-y-3">
                          {sessions.map((session, sessionIndex) => (
                            <div
                              key={`${session.course}-${session.index}-${sessionIndex}`}
                              className="rounded-lg bg-slate-900 p-3"
                            >
                              <p className="text-sm font-semibold">
                                {session.start}-{session.end}
                              </p>
                              <p className="mt-1 text-sm text-slate-300">
                                {session.course} {session.index}
                              </p>
                              <p className="text-xs text-slate-400">
                                {session.type} {session.group}
                              </p>
                              <p className="text-xs text-slate-500">
                                {session.venue}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-5">
                    <h4 className="font-semibold">Preference match</h4>
                    {timetable.explanations.length > 0 ? (
                      <ul className="mt-2 space-y-1 text-sm text-slate-400">
                        {timetable.explanations.slice(0, 6).map((note, i) => (
                          <li key={i}>• {note}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-slate-400">
                        This timetable matches your selected preferences well.
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </section>
        )}
      </div>
    </main>
  );
}
