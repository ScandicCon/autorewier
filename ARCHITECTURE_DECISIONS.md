# АРХИТЕКТУРНЫЕ РЕШЕНИЯ ДЛЯ СПРИНТА (3 недели)

---

## BACKEND ARCHITECTURE

### 1. Avito Parser — Retry & Resilience Pattern

**Current issues:**
- Captcha blocks на новых IP
- Timeout при медленной сети
- Нет graceful degradation

**Solution Architecture:**

```python
# app/services/parsers/avito.py

class AvitoParserConfig:
    MAX_RETRIES = 5
    RETRY_DELAY_MIN = 2  # сек
    RETRY_DELAY_MAX = 15
    TIMEOUT = 30
    BACKOFF_MULTIPLIER = 1.5

async def parse_avito_with_retry(url: str) -> ParsedListing | None:
    """
    Retry logic с exponential backoff.
    
    Strategies:
    1. Try fetch with current browser profile
    2. On timeout → wait 2s, retry (2x)
    3. On captcha → wait 10s, retry with different User-Agent
    4. On 403/429 → exponential backoff up to 15s
    5. On 3+ failures → return partial data with warning
    """
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            html = await fetch_avito_html(url, timeout=TIMEOUT)
            
            if is_blocked_html(html):
                if "captcha" in html:
                    log.warning(f"Captcha detected at attempt {attempt}")
                    if attempt < MAX_RETRIES:
                        delay = min(RETRY_DELAY_MAX, RETRY_DELAY_MIN * (2 ** attempt))
                        await asyncio.sleep(delay)
                        continue
                else:
                    # Other block (403, 429)
                    delay = RETRY_DELAY_MIN * (BACKOFF_MULTIPLIER ** attempt)
                    log.info(f"Blocked (attempt {attempt}), waiting {delay}s")
                    await asyncio.sleep(delay)
                    continue
            
            if not is_valid_listing_html(html):
                log.warning(f"Invalid HTML at {url}")
                break
            
            listing = _parse_listing_html(html)
            log.info(f"Success at attempt {attempt}")
            return listing
            
        except TimeoutError:
            log.warning(f"Timeout at attempt {attempt}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_MIN * attempt)
                continue
        except Exception as e:
            log.error(f"Parse error: {e}", exc_info=True)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_MIN)
                continue
    
    # Graceful degradation
    log.warning(f"All retries failed for {url}, returning None")
    return None
```

**Captcha Detection Heuristics:**
```python
def is_blocked_html(html: str) -> bool:
    """Check for common block indicators."""
    blocked_keywords = [
        'recaptcha', 'капча', 'подтвердите',
        '403 forbidden', 'access denied',
        'cloudflare', 'rate limit'
    ]
    html_lower = html.lower()
    return any(kw in html_lower for kw in blocked_keywords)
```

**Metrics to track:**
- `avito_parse_success_rate` (gauge, %)
- `avito_parse_latency_p95` (histogram, sec)
- `avito_captcha_hits` (counter)
- `avito_retry_count` (histogram)

---

### 2. Image Generation Service (Placeholder)

**Pattern:** Async generator + filesystem cache

```python
# app/services/image_generation.py (new file)

from PIL import Image, ImageDraw
from pathlib import Path
from datetime import datetime, timedelta

class PlaceholderImageGenerator:
    """
    Generates placeholder car images when user doesn't provide photo.
    Used as fallback in inspection creation flow.
    """
    
    CACHE_DIR = Path("data/placeholders")
    CACHE_TTL = timedelta(days=30)
    
    TEMPLATES = {
        "sedan": {"bg_color": "#E8F4F8", "icon": "🚗"},
        "suv": {"bg_color": "#D4E8D4", "icon": "🚙"},
        "van": {"bg_color": "#F0E8D4", "icon": "🚐"},
        "truck": {"bg_color": "#F8E0D4", "icon": "🚚"},
    }
    
    async def generate(self, 
                       car_type: str = "sedan",
                       color: str = "#333333",
                       width: int = 800,
                       height: int = 600) -> bytes:
        """
        Generate placeholder image.
        
        Args:
            car_type: sedan|suv|van|truck
            color: RGB hex color
            width, height: Image dimensions
        
        Returns:
            PNG bytes
        """
        
        # Check cache
        cache_key = f"{car_type}_{color}_{width}x{height}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached
        
        # Generate
        img = Image.new("RGB", (width, height), color=self.TEMPLATES[car_type]["bg_color"])
        draw = ImageDraw.Draw(img)
        
        # Draw simple car silhouette (placeholder)
        draw.rectangle(
            [(width * 0.2, height * 0.4), (width * 0.8, height * 0.6)],
            outline=color, width=3
        )
        
        # Cache
        png_bytes = self._to_png_bytes(img)
        await self._save_cached(cache_key, png_bytes)
        
        return png_bytes
    
    async def _get_cached(self, key: str) -> bytes | None:
        """Load from disk cache."""
        path = self.CACHE_DIR / f"{key}.png"
        if path.exists() and not self._is_expired(path):
            return path.read_bytes()
        return None
    
    async def _save_cached(self, key: str, data: bytes):
        """Save to disk cache."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (self.CACHE_DIR / f"{key}.png").write_bytes(data)

# Usage in InspectionComposer
generator = PlaceholderImageGenerator()
placeholder_bytes = await generator.generate(car_type="sedan")
```

**Integration points:**
1. Called from `POST /api/v1/inspection/{id}/upload-image` on failure
2. Frontend gets placeholder URL from response
3. User can replace later

---

### 3. Webhook for Analysis Status Synchronization

**Pattern:** Async webhook receiver + Redis queue + idempotency

```python
# app/api/routes.py (new endpoint)

from app.services.webhooks import WebhookService, WebhookSignature

router = APIRouter(prefix="/api/v1", tags=["inspection"])

@router.post("/inspection/{inspection_id}/status-webhook")
async def receive_status_webhook(
    inspection_id: int,
    body: dict,
    request: Request,
    session: AsyncSession = Depends(get_db),
    webhook_service: WebhookService = Depends(),
):
    """
    Receive status update from external analysis service.
    
    Payload:
    {
        "status": "completed|failed",
        "risk_score": 45.5,
        "error": "optional error message",
        "timestamp": "2026-06-08T10:30:00Z"
    }
    
    Headers (required):
    X-Webhook-Signature: HMAC-SHA256(payload, secret)
    X-Webhook-Timestamp: unix timestamp
    """
    
    # Verify signature
    signature = request.headers.get("X-Webhook-Signature")
    timestamp = request.headers.get("X-Webhook-Timestamp")
    
    if not await webhook_service.verify_signature(
        body=body,
        signature=signature,
        timestamp=timestamp
    ):
        log.warning(f"Invalid webhook signature for inspection {inspection_id}")
        raise HTTPException(401, "Invalid signature")
    
    # Check idempotency
    if await webhook_service.is_processed(
        inspection_id=inspection_id,
        webhook_id=body.get("id")  # External service should provide ID
    ):
        log.info(f"Webhook already processed for inspection {inspection_id}")
        return {"status": "already_processed"}
    
    # Queue for processing
    await webhook_service.enqueue(inspection_id, body)
    
    return {"status": "accepted", "inspection_id": inspection_id}

# app/services/webhooks.py (new file)

class WebhookService:
    """Webhook handling with signature verification and idempotency."""
    
    def __init__(self, redis: aioredis.Redis, db: AsyncSession):
        self.redis = redis
        self.db = db
        self.webhook_secret = settings.webhook_secret
    
    async def verify_signature(self, body: dict, signature: str, timestamp: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        import hashlib
        import hmac
        import time
        
        # Prevent replay attacks
        request_time = int(timestamp)
        if abs(time.time() - request_time) > 300:  # 5 min window
            return False
        
        payload = json.dumps(body, separators=(',', ':'), sort_keys=True)
        expected_sig = hmac.new(
            self.webhook_secret.encode(),
            f"{timestamp}.{payload}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_sig)
    
    async def is_processed(self, inspection_id: int, webhook_id: str) -> bool:
        """Check idempotency key."""
        key = f"webhook:processed:{inspection_id}:{webhook_id}"
        return await self.redis.exists(key)
    
    async def enqueue(self, inspection_id: int, payload: dict):
        """Add to processing queue."""
        await self.redis.rpush(
            "queue:webhook:analysis",
            json.dumps({"inspection_id": inspection_id, "payload": payload})
        )

# app/workers/worker.py (process webhook queue)

async def process_webhook_queue():
    """Background worker to process analysis webhooks."""
    
    while True:
        item = await redis.blpop("queue:webhook:analysis", timeout=5)
        if not item:
            continue
        
        data = json.loads(item[1])
        inspection_id = data["inspection_id"]
        payload = data["payload"]
        
        try:
            inspection = await db.get(Inspection, inspection_id)
            inspection.risk_score = payload.get("risk_score")
            inspection.status = InspectionStage.POST_INSPECTION
            inspection.analysis_complete_at = datetime.utcnow()
            
            if payload.get("status") == "failed":
                inspection.analysis_error = payload.get("error")
            
            await db.commit()
            
            # Mark as processed
            webhook_id = payload.get("id")
            await redis.setex(
                f"webhook:processed:{inspection_id}:{webhook_id}",
                3600,  # 1 hour TTL
                "1"
            )
            
            log.info(f"Webhook processed for inspection {inspection_id}")
            
        except Exception as e:
            log.error(f"Error processing webhook: {e}", exc_info=True)
            # Re-queue for retry
            await redis.rpush("queue:webhook:analysis", item[1])
```

**Testing:**
```python
# tests/test_webhook.py

@pytest.mark.asyncio
async def test_webhook_signature_verification():
    """Valid signature passes."""
    service = WebhookService(redis, db)
    payload = {"status": "completed", "risk_score": 45}
    signature = hmac.new(
        settings.webhook_secret.encode(),
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()
    
    assert await service.verify_signature(payload, signature, str(int(time.time())))

@pytest.mark.asyncio
async def test_webhook_idempotency():
    """Same webhook processed only once."""
    service = WebhookService(redis, db)
    webhook_id = "ext_123"
    
    assert not await service.is_processed(1, webhook_id)
    await service.enqueue(1, {"id": webhook_id})
    # Process
    await db.execute("UPDATE inspections SET risk_score = 45 WHERE id = 1")
    await service.mark_processed(1, webhook_id)
    
    assert await service.is_processed(1, webhook_id)
```

---

## FRONTEND ARCHITECTURE

### 1. Layout System with CSS Variables

**Problem:** Emoji in forms, inconsistent font sizes, poor mobile layout

**Solution:**
```css
/* frontend/src/styles/design-system.css (create) */

:root {
  /* Typography */
  --font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, sans-serif;
  --font-family-mono: "Monaco", "Menlo", "Ubuntu Mono", monospace;
  
  --font-size-xs: 11px;
  --font-size-sm: 12px;
  --font-size-base: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 20px;
  --font-size-2xl: 24px;
  --font-size-3xl: 32px;
  
  --line-height-tight: 1.3;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.75;
  
  /* Spacing */
  --spacing-2xs: 4px;
  --spacing-xs: 8px;
  --spacing-sm: 12px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --spacing-2xl: 48px;
  
  /* Colors */
  --color-primary: #2563eb;
  --color-primary-dark: #1e40af;
  --color-primary-light: #dbeafe;
  
  --color-error: #dc2626;
  --color-success: #16a34a;
  --color-warning: #ea580c;
  
  --color-neutral-50: #f9fafb;
  --color-neutral-100: #f3f4f6;
  --color-neutral-500: #6b7280;
  --color-neutral-900: #111827;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  
  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-full: 9999px;
}

/* Base Typography */
body {
  font-family: var(--font-family-base);
  font-size: var(--font-size-base);
  line-height: var(--line-height-normal);
  color: var(--color-neutral-900);
  background-color: var(--color-neutral-50);
}

h1 { font-size: var(--font-size-3xl); font-weight: 700; line-height: var(--line-height-tight); }
h2 { font-size: var(--font-size-2xl); font-weight: 700; }
h3 { font-size: var(--font-size-xl); font-weight: 600; }

/* Minimum text size enforcement */
p, span, label, button, input, textarea {
  font-size: var(--font-size-base); /* min 14px */
}

/* Responsive breakpoints */
@media (max-width: 640px) {
  :root {
    --font-size-base: 16px; /* Increase on mobile for better readability */
    --spacing-md: 12px;
  }
}

@media (max-width: 768px) {
  h1 { font-size: var(--font-size-2xl); }
  h2 { font-size: var(--font-size-xl); }
}
```

**Apply in components:**
```vue
<!-- frontend/src/components/AuthModal.vue -->
<template>
  <div class="auth-modal">
    <h2 class="title">Sign In</h2>
    <form @submit.prevent="handleLogin">
      <div class="form-group">
        <label for="email">Email</label>
        <input 
          id="email"
          v-model="email" 
          type="email"
          class="input"
          aria-label="Email address"
        />
      </div>
      <button type="submit" class="btn btn-primary">
        Sign In
      </button>
    </form>
  </div>
</template>

<style scoped>
.auth-modal {
  padding: var(--spacing-lg);
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.title {
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.form-group {
  margin-bottom: var(--spacing-md);
}

label {
  display: block;
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-base);
  font-weight: 500;
}

.input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-size-base);
  border: 1px solid var(--color-neutral-200);
  border-radius: var(--radius-md);
}

.btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  font-size: var(--font-size-base);
  border-radius: var(--radius-md);
  transition: all 0.2s;
}

.btn-primary {
  background-color: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background-color: var(--color-primary-dark);
}

/* Mobile optimization */
@media (max-width: 640px) {
  .auth-modal {
    padding: var(--spacing-md);
  }
  
  .btn {
    width: 100%;
    min-height: 44px; /* Touch target */
  }
}
</style>
```

---

### 2. Custom Checkbox Component (No emoji)

**Problem:** Native checkbox doesn't match design, can't remove emoji

**Solution:**
```vue
<!-- frontend/src/components/Checkbox.vue (new) -->
<template>
  <label class="checkbox-wrapper" :class="{ disabled }">
    <input 
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      class="checkbox-input"
      @change="$emit('update:modelValue', $event.target.checked)"
      :aria-label="label"
    />
    <span class="checkbox-visual">
      <svg v-if="modelValue" class="checkmark" viewBox="0 0 20 20">
        <path d="M7 10l2 2 4-4" stroke="white" stroke-width="2" fill="none" />
      </svg>
    </span>
    <span class="checkbox-label">{{ label }}</span>
  </label>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  label: string;
  disabled?: boolean;
}>();

defineEmits<{
  'update:modelValue': [value: boolean];
}>();
</script>

<style scoped>
.checkbox-wrapper {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-size: var(--font-size-base);
  gap: var(--spacing-sm);
}

.checkbox-wrapper.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.checkbox-input {
  display: none; /* Hide native checkbox */
}

.checkbox-visual {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-neutral-300);
  border-radius: var(--radius-sm);
  background-color: white;
  transition: all 0.2s;
  flex-shrink: 0;
}

.checkbox-input:checked + .checkbox-visual {
  background-color: var(--color-primary);
  border-color: var(--color-primary);
}

.checkbox-input:focus + .checkbox-visual {
  outline: 2px solid var(--color-primary-light);
  outline-offset: 2px;
}

.checkbox-label {
  font-size: var(--font-size-base);
  user-select: none;
}

.checkmark {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}
</style>
```

**Usage:**
```vue
<!-- frontend/src/views/RegisterView.vue -->
<template>
  <Checkbox 
    v-model="agreedToTerms"
    label="I agree to the Terms of Service"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Checkbox from '@/components/Checkbox.vue';

const agreedToTerms = ref(false);
</script>
```

---

### 3. Image Upload with Fallback

**Component structure:**
```vue
<!-- frontend/src/components/ImageUpload.vue (new) -->
<template>
  <div class="image-upload">
    <div 
      v-if="!uploadedImage"
      class="upload-zone"
      @dragover="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="handleDrop"
      :class="{ dragging: isDragging }"
    >
      <svg class="upload-icon" viewBox="0 0 24 24">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <p class="upload-text">Drag and drop images or click to select</p>
      <input 
        type="file"
        ref="fileInput"
        multiple
        accept="image/*"
        style="display: none"
        @change="handleFileSelect"
      />
      <button 
        type="button"
        class="btn btn-secondary"
        @click="fileInput?.click()"
      >
        Select Files
      </button>
    </div>
    
    <div v-else class="uploaded-content">
      <div class="preview-grid">
        <div v-for="file in uploadedFiles" :key="file.name" class="preview-item">
          <img :src="file.preview" :alt="file.name" />
          <button 
            type="button"
            class="btn-remove"
            @click="removeFile(file.name)"
          >
            Remove
          </button>
        </div>
      </div>
      
      <div v-if="isUploading" class="upload-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: uploadProgress + '%' }" />
        </div>
        <p>{{ uploadProgress }}%</p>
      </div>
      
      <div v-if="uploadError" class="error-message">
        {{ uploadError }}
        <button type="button" @click="retryUpload" class="btn-retry">
          Retry
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useInspectionApi } from '@/composables/useInspectionApi';

const props = defineProps<{
  inspectionId: number;
}>();

const emit = defineEmits<{
  'upload-complete': [files: string[]];
  'upload-failed': [error: string];
}>();

const fileInput = ref<HTMLInputElement>();
const isDragging = ref(false);
const uploadedFiles = ref<Array<{ name: string; preview: string }>>([]);
const isUploading = ref(false);
const uploadProgress = ref(0);
const uploadError = ref('');

const uploadedImage = computed(() => uploadedFiles.value.length > 0);

const { uploadImages } = useInspectionApi();

const handleDrop = async (e: DragEvent) => {
  isDragging.value = false;
  const files = e.dataTransfer?.files;
  if (files) {
    await processFiles(Array.from(files));
  }
};

const handleFileSelect = async (e: Event) => {
  const files = (e.target as HTMLInputElement).files;
  if (files) {
    await processFiles(Array.from(files));
  }
};

const processFiles = async (files: File[]) => {
  const validFiles = files.filter(f => {
    if (!f.type.startsWith('image/')) {
      uploadError.value = 'Only image files allowed';
      return false;
    }
    if (f.size > 5 * 1024 * 1024) {
      uploadError.value = 'File size must be less than 5MB';
      return false;
    }
    return true;
  });
  
  if (validFiles.length === 0) return;
  
  // Preview
  for (const file of validFiles) {
    const reader = new FileReader();
    reader.onload = (e) => {
      uploadedFiles.value.push({
        name: file.name,
        preview: e.target?.result as string,
      });
    };
    reader.readAsDataURL(file);
  }
  
  // Upload
  await uploadImages(props.inspectionId, validFiles);
};

const removeFile = (name: string) => {
  uploadedFiles.value = uploadedFiles.value.filter(f => f.name !== name);
};

const retryUpload = async () => {
  uploadError.value = '';
  if (uploadedFiles.value.length > 0) {
    // Re-upload logic
  }
};
</script>

<style scoped>
.image-upload {
  width: 100%;
}

.upload-zone {
  border: 2px dashed var(--color-neutral-300);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  text-align: center;
  transition: all 0.2s;
}

.upload-zone.dragging {
  border-color: var(--color-primary);
  background-color: var(--color-primary-light);
}

.upload-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--spacing-md);
  stroke: var(--color-neutral-400);
  stroke-width: 1.5;
  fill: none;
}

.upload-text {
  margin-bottom: var(--spacing-md);
  color: var(--color-neutral-600);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--spacing-md);
}

.preview-item {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--color-neutral-100);
}

.preview-item img {
  width: 100%;
  height: 120px;
  object-fit: cover;
}

.btn-remove {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  padding: var(--spacing-xs);
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-size-sm);
}

.upload-progress {
  margin-top: var(--spacing-md);
}

.progress-bar {
  height: 4px;
  background: var(--color-neutral-200);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.3s;
}

.error-message {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: #fee;
  border-radius: var(--radius-md);
  color: var(--color-error);
}

@media (max-width: 640px) {
  .upload-zone {
    padding: var(--spacing-lg);
  }
  
  .preview-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
```

---

## TESTING ARCHITECTURE

### Test Pyramid

```
            E2E Tests (10%)
          Integration Tests (30%)
      Unit & Component Tests (60%)
```

**Test organization:**
```
tests/
├── unit/
│   ├── test_parsers.py       # Parser unit tests
│   ├── test_analysis.py       # Risk scoring logic
│   └── test_webhooks.py       # Webhook signature verification
├── integration/
│   ├── test_api_regression.py # API contract tests
│   ├── test_auth_flow.py      # Registration → login flow
│   └── test_database.py       # Database operations
├── e2e/
│   ├── test_full_flow.py      # User journey
│   └── test_playwright.py     # UI automation (optional)
└── fixtures/
    ├── conftest.py            # Shared fixtures
    ├── users.py               # User factory
    └── inspections.py         # Inspection factory
```

**CI/CD trigger:**
```yaml
# .github/workflows/test.yml
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      # Unit tests (fast, always run)
      - run: pytest tests/unit -v
      
      # Integration tests (medium speed)
      - run: pytest tests/integration -v
      
      # E2E tests (slow, only on main/PR)
      - run: pytest tests/e2e -v
        if: github.event_name == 'push' || github.base_ref == 'main'
      
      - run: npm run test  # frontend tests
```

---

## INFRASTRUCTURE

### Services & Dependencies

```yaml
# docker-compose.yml (with worker)

services:
  api:
    image: autorewier-api:latest
    ports: ["8000:8000"]
    env_file: .env
    healthcheck:
      test: curl -f http://127.0.0.1:8000/api/v1/health
      interval: 20s
      retries: 5

  worker:
    image: autorewier-api:latest
    command: python -m app.workers.worker
    depends_on:
      api:
        condition: service_healthy
    env_file: .env

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: postgres:15-alpine
    env_file: .env
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

---

## DEPLOYMENT CHECKLIST (Week 3)

- [ ] Run full test suite (unit + integration + e2e)
- [ ] Performance benchmark (LCP, bundle size)
- [ ] Security audit (OWASP Top 10)
- [ ] Database migration test (dev → staging)
- [ ] Logs reviewed (no ERRORs or WARNINGs)
- [ ] Monitoring alerts configured (error rate, latency p95)
- [ ] Rollback plan documented
- [ ] Team trained on runbooks
- [ ] Launch approval from stakeholders

**Success criteria:** Zero critical issues, >95% API success rate
