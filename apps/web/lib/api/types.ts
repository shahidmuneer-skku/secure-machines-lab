import type { Schemas } from "./client"

export type Job = Schemas["JobList"]
export type JobDetail = Schemas["JobDetail"]
export type JobStatus = Job["status"]
export type Verdict = NonNullable<Job["verdict"]>
export type MediaObject = Schemas["Media"]
export type ApiKey = Schemas["ApiKey"]
export type ApiKeyCreated = Schemas["ApiKeyCreated"]
export type LedgerEntry = Schemas["LedgerEntry"]
export type Balance = Schemas["Balance"]
export type Report = Schemas["Report"]
export type Payment = Schemas["Payment"]
export type Subscription = Schemas["Subscription"]
export type CreditPack = Schemas["CreditPack"]
export type Plan = Schemas["Plan"]
export type Me = Schemas["Me"]
export type Explanation = Schemas["Explanation"]

// What users see of a job: generic steps and evidence, never the detectors behind them.
export type JobStep = JobDetail["steps"][number]
export type JobCheck = JobDetail["checks"][number]
export type Provenance = NonNullable<JobDetail["provenance"]>
export type TimelinePoint = JobDetail["timeline"][number]
export type JobArtifact = JobDetail["artifacts"][number]
export type TimelineEvent = JobDetail["events"][number]
