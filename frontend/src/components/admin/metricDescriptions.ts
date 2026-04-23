/**
 * Human-readable metric names and how they were calculated.
 * Shown on hover in the admin dashboard.
 */
export const METRIC_DESCRIPTIONS: Record<string, { name: string; description: string }> = {
  // Usage
  'usage.daily_active_users': {
    name: 'Daily active users',
    description: 'Number of unique users who had at least one chat session today.',
  },
  'usage.weekly_active_users': {
    name: 'Weekly active users',
    description: 'Number of unique users who had at least one chat session in the last 7 days.',
  },
  'usage.activated_users': {
    name: 'Activated users',
    description: 'Number of users who have ever started at least one chat session.',
  },
  'usage.total_users': {
    name: 'Total users',
    description: 'Total number of user accounts in the system.',
  },
  'usage.activation_rate': {
    name: 'Activation rate',
    description: 'Percentage of all users who have started at least one session (activated users ÷ total users × 100).',
  },
  'usage.queries_per_clinician': {
    name: 'Average queries per user',
    description: 'Average number of user messages (queries) per user in the selected period.',
  },
  'usage.sessions_per_user': {
    name: 'Average sessions per user',
    description: 'Average number of chat sessions per user in the selected period.',
  },
  'usage.retention_week1_to_week3': {
    name: 'Retention rate',
    description: 'Of users active in week 1 (7–14 days ago), the percentage who were also active in week 3 (last 7 days).',
  },
  // Clinical value
  'clinical_value.helpful_feedback_percentage': {
    name: 'Helpful feedback',
    description: 'Percentage of all feedback that was marked as helpful.',
  },
  'clinical_value.avg_usefulness_score': {
    name: 'Average usefulness score',
    description: 'Average rating (1–5) given by users when submitting feedback.',
  },
  'clinical_value.relevant_queries_percentage': {
    name: 'Relevant queries',
    description: 'From surveys: percentage of queries users said were relevant to their work.',
  },
  'clinical_value.avg_time_saved_minutes': {
    name: 'Average time saved',
    description: 'From surveys: average minutes saved per session reported by users.',
  },
  // Safety
  'safety.flags_per_100_queries': {
    name: 'Flags per 100 queries',
    description: 'Safety flags per 100 user queries. Lower is better.',
  },
  'safety.open_safety_events': {
    name: 'Open safety events',
    description: 'Number of safety events currently in open status.',
  },
  'safety.critical_incidents': {
    name: 'Critical incidents',
    description: 'Number of safety events marked as critical.',
  },
  'safety.citations_percentage': {
    name: 'Responses with citations',
    description: 'Percentage of AI responses that included guideline citations.',
  },
  'safety.red_flag_accuracy_percentage': {
    name: 'Red-flag accuracy',
    description: 'Of red-flag queries, percentage that were correctly flagged.',
  },
  // PMF
  'pmf.heavy_users': {
    name: 'Heavy users',
    description: 'Users with more than 20 queries in the last 7 days.',
  },
  'pmf.very_disappointed_percentage': {
    name: 'Very disappointed',
    description: 'Percentage of PMF respondents who said they would be very disappointed without the product. Higher indicates stronger product-market fit.',
  },
  'pmf.avg_pmf_score': {
    name: 'Average PMF score',
    description: 'Average score from Product-Market Fit surveys (out of 10).',
  },
  // Devices
  'devices.by_type': {
    name: 'Device breakdown',
    description: 'Number of logins and session starts by device type (phone, tablet, laptop).',
  },
  // AI Response
  'ai_response.total_responses': {
    name: 'Total AI responses',
    description: 'Total number of AI-generated responses in the period.',
  },
  'ai_response.helpful_percentage': {
    name: 'Helpful responses',
    description: 'Percentage of feedback-rated responses that users marked as helpful.',
  },
  'ai_response.avg_rating': {
    name: 'Average rating',
    description: 'Average user rating (1–5) for AI responses that received feedback.',
  },
  'ai_response.avg_response_time_ms': {
    name: 'Average response time',
    description: 'Average time in milliseconds for the AI to generate a response.',
  },
  // Surveys
  'surveys.completion_percentage': {
    name: 'Survey completion rate',
    description: 'Percentage of total users who completed at least one survey.',
  },
}
