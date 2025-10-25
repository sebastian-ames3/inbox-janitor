const CONFIG = {
  // 🔒 SAFE MODE: Set to false after 7 days of testing
  SAFE_MODE: true,
  
  // Your classifier API URL from Codespaces
  // Example: https://your-codespace-8000.app.github.dev
  CLASSIFIER_URL: "https://inbox-janitor-production.up.railway.app/classify",
  
  // Labels
  LABELS: {
    REVIEW: "Review-7d",
    JANITOR_LOG: "Janitor-Log",
    ARCHIVE_ONLY: "Archive-Only"  // Manual override
  },
  
  // Processing limits
  MAX_EMAILS_PER_RUN: 50,  // Don't process too many at once
  
  // Filter for Safe Mode testing (only promotions category)
  SAFE_MODE_FILTER: "label:inbox category:promotions newer_than:1d"
};

// ============================================
// Main Processing Function
// ============================================

function processInbox() {
  Logger.log("🧹 Inbox Janitor starting...");
  Logger.log(`🔒 Safe Mode: ${CONFIG.SAFE_MODE ? "ON (archive only)" : "OFF (can trash)"}`);
  
  try {
    // Get emails to process
    const searchQuery = CONFIG.SAFE_MODE 
      ? CONFIG.SAFE_MODE_FILTER 
      : "label:inbox newer_than:7d";
    
    const threads = GmailApp.search(searchQuery, 0, CONFIG.MAX_EMAILS_PER_RUN);
    Logger.log(`📬 Found ${threads.length} threads to process`);
    
    if (threads.length === 0) {
      Logger.log("✅ No emails to process");
      return;
    }
    
    // Get or create labels
    const reviewLabel = getOrCreateLabel(CONFIG.LABELS.REVIEW);
    const logLabel = getOrCreateLabel(CONFIG.LABELS.JANITOR_LOG);
    
    // Process each thread
    let stats = { keep: 0, archive: 0, trash: 0, review: 0, errors: 0 };
    
    threads.forEach(thread => {
      try {
        const result = processThread(thread, reviewLabel, logLabel);
        stats[result]++;
      } catch (error) {
        Logger.log(`❌ Error processing thread: ${error}`);
        stats.errors++;
      }
    });
    
    // Log results
    Logger.log("\n📊 Results:");
    Logger.log(`  ✅ Keep: ${stats.keep}`);
    Logger.log(`  📦 Archive: ${stats.archive}`);
    Logger.log(`  🗑️ Trash: ${stats.trash}`);
    Logger.log(`  🔍 Review: ${stats.review}`);
    Logger.log(`  ❌ Errors: ${stats.errors}`);
    Logger.log("\n🧹 Inbox Janitor finished!");
    
    return stats;
    
  } catch (error) {
    Logger.log(`💥 Fatal error: ${error}`);
    throw error;
  }
}

// ============================================
// Process Single Thread
// ============================================

function processThread(thread, reviewLabel, logLabel) {
  const messages = thread.getMessages();
  const firstMessage = messages[0];  // Use first message for classification
  
  // Extract metadata
  const metadata = {
     from_address: firstMessage.getFrom(),
     subject: firstMessage.getSubject(),
     snippet: firstMessage.getBody().substring(0, 200).replace(/<[^>]*>/g, ''),
     is_starred: thread.hasStarredMessages(),
     is_contact: isFromContact(firstMessage.getFrom()),
     date_days_ago: getDaysAgo(firstMessage.getDate())
   };
  
  // Check for manual override label
  const labels = thread.getLabels();
  const hasArchiveOnly = labels.some(l => l.getName() === CONFIG.LABELS.ARCHIVE_ONLY);
  
  if (hasArchiveOnly) {
    thread.moveToArchive();
    thread.addLabel(logLabel);
    Logger.log(`📦 [MANUAL OVERRIDE] Archived: ${metadata.subject}`);
    return "archive";
  }
  
  // Call classifier API
  const classification = classifyEmail(metadata);
  
  // Apply action based on classification
  const action = applyAction(thread, classification, reviewLabel, logLabel);
  
  Logger.log(`${getActionEmoji(action)} [${action.toUpperCase()}] ${metadata.subject.substring(0, 50)}... (${classification.reason})`);
  
  return action;
}

// ============================================
// Classifier API Call
// ============================================

function classifyEmail(metadata) {
  try {
    const response = UrlFetchApp.fetch(CONFIG.CLASSIFIER_URL, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(metadata),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() !== 200) {
      throw new Error(`API returned ${response.getResponseCode()}`);
    }
    
    return JSON.parse(response.getContentText());
    
  } catch (error) {
    Logger.log(`⚠️ Classifier API error: ${error}. Defaulting to REVIEW.`);
    return {
      action: "review",
      reason: `API error: ${error}`,
      confidence: 0.0
    };
  }
}

// ============================================
// Apply Action to Thread
// ============================================

function applyAction(thread, classification, reviewLabel, logLabel) {
  let action = classification.action;
  
  // SAFE MODE: Convert trash → archive
  if (CONFIG.SAFE_MODE && action === "trash") {
    Logger.log(`  🔒 Safe Mode: Converting TRASH → ARCHIVE`);
    action = "archive";
  }
  
  // Apply the action
  switch (action) {
    case "keep":
      // Do nothing, stays in inbox
      thread.addLabel(logLabel);
      break;
      
    case "archive":
      thread.moveToArchive();
      thread.addLabel(logLabel);
      break;
      
    case "trash":
      // Only executed if SAFE_MODE is false
      thread.moveToTrash();  // Recoverable for 30 days
      thread.addLabel(logLabel);
      break;
      
    case "review":
      thread.addLabel(reviewLabel);
      thread.addLabel(logLabel);
      break;
  }
  
  return action;
}

// ============================================
// Helper Functions
// ============================================

function getOrCreateLabel(labelName) {
  let label = GmailApp.getUserLabelByName(labelName);
  if (!label) {
    label = GmailApp.createLabel(labelName);
    Logger.log(`📝 Created label: ${labelName}`);
  }
  return label;
}

function isFromContact(fromAddress) {
  // Extract email from "Name <email@domain.com>" format
  const emailMatch = fromAddress.match(/<(.+?)>/);
  const email = emailMatch ? emailMatch[1] : fromAddress;
  
  try {
    const contacts = ContactsApp.getContactsByEmailAddress(email);
    return contacts.length > 0;
  } catch (error) {
    return false;
  }
}

function getDaysAgo(date) {
  const now = new Date();
  const diffMs = now - date;
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function getActionEmoji(action) {
  const emojis = {
    keep: "✅",
    archive: "📦",
    trash: "🗑️",
    review: "🔍"
  };
  return emojis[action] || "❓";
}

// ============================================
// Manual Test Function (Run this first!)
// ============================================

function testClassifier() {
  Logger.log("🧪 Testing classifier API connection...");
  
  const testEmail = {
    from_address: "newsletter@example.com",
    subject: "Weekly Newsletter - Updates",
    snippet: "Check out this week's top stories...",
    is_starred: false,
    is_contact: false,
    date_days_ago: 1
  };
  
  try {
    const result = classifyEmail(testEmail);
    Logger.log("✅ Classifier working!");
    Logger.log(`   Action: ${result.action}`);
    Logger.log(`   Reason: ${result.reason}`);
    Logger.log(`   Confidence: ${result.confidence}`);
  } catch (error) {
    Logger.log(`❌ Test failed: ${error}`);
  }
}

// ============================================
// Daily Digest Email (Optional)
// ============================================

function sendDailySummary() {
  const stats = processInbox();
  
  const emailBody = `
<h2>🧹 Inbox Janitor Daily Report</h2>
<p><strong>Safe Mode:</strong> ${CONFIG.SAFE_MODE ? "✅ ON" : "⚠️ OFF"}</p>

<h3>Actions Taken:</h3>
<ul>
  <li>✅ Keep: ${stats.keep}</li>
  <li>📦 Archive: ${stats.archive}</li>
  <li>🗑️ Trash: ${stats.trash}</li>
  <li>🔍 Review: ${stats.review}</li>
  <li>❌ Errors: ${stats.errors}</li>
</ul>

<p><em>Check emails labeled "Review-7d" in Gmail.</em></p>
  `;
  
  GmailApp.sendEmail(
    Session.getActiveUser().getEmail(),
    "📊 Inbox Janitor Daily Summary",
    "",
    { htmlBody: emailBody }
  );
  
  Logger.log("📧 Daily summary email sent!");
}
