const $=s=>document.querySelector(s);
const API_BASE = 'https://borodat-panel.onrender.com';
const backendMediaUrl = value => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, API_BASE);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
  } catch (_) {
    return '';
  }
};
const $$=s=>document.querySelectorAll(s);

/* Independent cart open/close delegation */
document.addEventListener('click', event => {
  const overlay = document.getElementById('cartOverlay');
  if (!overlay) return;

  if (event.target.closest('.add-cart')) return;

  if (event.target.closest('.cart')) {
    event.preventDefault();
    overlay.classList.add('open');
    document.body.classList.add('cart-open');
  } else if (
    event.target.closest('#closeCart') ||
    event.target === overlay
  ) {
    overlay.classList.remove('open');
    document.body.classList.remove('cart-open');
  }
});


const menu=$('#mobileMenu');
$('#menuBtn').onclick=()=>menu.classList.add('open');
$('#closeMenu').onclick=()=>menu.classList.remove('open');
$$('.mobile-menu a').forEach(a=>a.onclick=()=>menu.classList.remove('open'));

let slide = 0;
let slides = [...document.querySelectorAll('.hero-slide')];
const dots = $('#heroDots');
const heroTrack = $('#heroTrack');

function showSlide(i) {
  if (!slides.length) return;
  slide = (i + slides.length) % slides.length;
  slides.forEach((item, n) => item.classList.toggle('active', n === slide));
  [...dots.children].forEach((item, n) => item.classList.toggle('active', n === slide));
}

slides.forEach((_, i) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.setAttribute('aria-label', 'اسلاید ' + (i + 1));
  b.onclick = () => {
    showSlide(i);
    restartHeroTimer();
  };
  dots.appendChild(b);
});

showSlide(0);

let heroTimer;
function restartHeroTimer() {
  clearInterval(heroTimer);
  if (slides.length > 1) {
    heroTimer = setInterval(() => showSlide(slide + 1), 5000);
  }
}

restartHeroTimer();

function renderPanelSlides(items) {
  if (!Array.isArray(items) || !items.length || !heroTrack) return;

  const escSlide = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);

  const safeLink = value => {
    const raw = String(value || '#latest').trim();
    try {
      const url = new URL(raw, window.location.origin);
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '#latest';
    } catch (_) {
      return '#latest';
    }
  };

  heroTrack.innerHTML = items.map((item, index) => {
    const image = backendMediaUrl(item.image_url);
    const title = escSlide(item.title || 'فروشگاه دکتر برودت');
    const description = escSlide(item.description || '');
    const buttonText = escSlide(item.button_text || 'مشاهده محصولات');
    const buttonUrl = escSlide(safeLink(item.button_url));
    return `<article class="hero-slide${index === 0 ? ' active' : ''}">
      ${image ? `<img src="${escSlide(image)}" alt="${title}" loading="lazy">` : ''}
      <div class="hero-copy">
        <h2>${title}</h2>
        ${description ? `<p>${description}</p>` : ''}
        <a href="${buttonUrl}" class="red-btn">${buttonText}</a>
      </div>
    </article>`;
  }).join('');

  slides = [...heroTrack.querySelectorAll('.hero-slide')];
  if (dots) {
    dots.innerHTML = '';
    slides.forEach((_, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.setAttribute('aria-label', 'اسلاید ' + (index + 1));
      button.onclick = () => {
        showSlide(index);
        restartHeroTimer();
      };
      dots.appendChild(button);
    });
  }
  showSlide(0);
  restartHeroTimer();
}

$$('.hero-arrow').forEach(button => {
  button.addEventListener('click', () => {
    showSlide(slide + (Number(button.dataset.dir) || 1));
    restartHeroTimer();
  });
});

let swipeStartX = 0;
let swipeStartY = 0;
let isSwiping = false;

heroTrack.addEventListener('pointerdown', e => {
  swipeStartX = e.clientX;
  swipeStartY = e.clientY;
  isSwiping = true;
  heroTrack.setPointerCapture(e.pointerId);
});

heroTrack.addEventListener('pointerup', e => {
  if (!isSwiping) return;
  isSwiping = false;

  const dx = e.clientX - swipeStartX;
  const dy = e.clientY - swipeStartY;

  if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
    showSlide(slide + (dx < 0 ? 1 : -1));
    restartHeroTimer();
  }
});

heroTrack.addEventListener('pointercancel', () => {
  isSwiping = false;
});

$$('[data-scroll]').forEach(b=>b.onclick=()=>{
 const el=document.getElementById(b.dataset.scroll);
 el.scrollBy({left:Number(b.dataset.dir)*el.clientWidth*.8,behavior:'smooth'});
});

$$('.product-track,.blog-track').forEach(el=>{
 let down=false,startX=0,scroll=0;
 el.addEventListener('pointerdown',e=>{
  down=true;
  startX=e.clientX;
  scroll=el.scrollLeft;
 });
 el.addEventListener('pointerup',()=>down=false);
 el.addEventListener('pointercancel',()=>down=false);
 el.addEventListener('pointermove',e=>{
  if(!down)return;
  el.scrollLeft=scroll-(e.clientX-startX);
 });
});

/* Persistent shopping cart */
const CART_KEY = 'drBorudatCart';
let cart = [];
try {
  const saved = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
  if (Array.isArray(saved)) cart = saved.filter(x =>
    x && typeof x.name === 'string' &&
    Number.isFinite(Number(x.price)) &&
    Number.isInteger(Number(x.qty)) &&
    Number(x.price) > 0 && Number(x.qty) > 0
  ).map(x => ({name:x.name, price:Number(x.price), qty:Number(x.qty)}));
} catch (_) { cart = []; }

const normalizeDigits = value => String(value)
  .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
  .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));

const readPrice = value => Math.round((Number(normalizeDigits(value).replace(/[^\d]/g, '')) || 0) / 10);
const formatMoney = value => Math.round(value * 10).toLocaleString('fa-IR') + ' ریال';

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function renderCart() {
  const count = cart.reduce((sum, item) => sum + item.qty, 0);
  $('#cartCount').textContent = count.toLocaleString('fa-IR');

  $('#cartItems').innerHTML = cart.map((item, index) => `
    <article class="cart-row">
      <div>
        <h3>${item.name}</h3>
        <div class="cart-price">${formatMoney(item.price)} برای هر عدد</div>
        <div class="cart-line-total">${formatMoney(item.price * item.qty)}</div>
      </div>
      <div class="cart-controls">
        <button type="button" data-cart-action="plus" data-index="${index}">+</button>
        <b>${item.qty.toLocaleString('fa-IR')}</b>
        <button type="button" data-cart-action="minus" data-index="${index}">−</button>
        <button type="button" class="cart-remove" data-cart-action="remove" data-index="${index}" aria-label="حذف">×</button>
      </div>
    </article>
  `).join('');

  $('#cartEmpty').classList.toggle('show', cart.length === 0);
  $('#cartFooter').style.display = cart.length ? 'block' : 'none';
  $('#cartTotal').textContent = formatMoney(
    cart.reduce((sum, item) => sum + item.price * item.qty, 0)
  );
}

function openCart() {
  $('#cartOverlay').classList.add('open');
  document.body.classList.add('cart-open');
}

function closeCart() {
  $('#cartOverlay').classList.remove('open');
  document.body.classList.remove('cart-open');
}

$$('.add-cart').forEach(button => {
  button.addEventListener('click', event => {
    event.preventDefault();
    event.stopImmediatePropagation();

    const card = button.closest('.product-card');
    if (!card) return;

    const name = card.querySelector('h3')?.textContent.trim();
    const price = readPrice(card.querySelector('.price')?.textContent || '');

    if (!name || !price) {
      alert('نام یا قیمت این محصول مشخص نیست.');
      return;
    }

    const existing = cart.find(item => item.name === name && item.price === price);
    if (existing) existing.qty += 1;
    else cart.push({name, price, qty:1});

    saveCart();
    renderCart();

  });
});

$('#cartItems').addEventListener('click', event => {
  const button = event.target.closest('[data-cart-action]');
  if (!button) return;

  const index = Number(button.dataset.index);
  const item = cart[index];
  if (!item) return;

  if (button.dataset.cartAction === 'plus') item.qty += 1;
  if (button.dataset.cartAction === 'minus') item.qty -= 1;
  if (button.dataset.cartAction === 'remove' || item.qty <= 0) {
    cart.splice(index, 1);
  }

  saveCart();
  renderCart();
});

$('.cart').addEventListener('click', openCart);

$$('.bottom-nav a').forEach(link => {
  if (link.textContent.includes('سبد خرید')) {
    link.addEventListener('click', event => {
      event.preventDefault();
      openCart();
    });
  }
});

$('#closeCart').addEventListener('click', closeCart);
$('#cartOverlay').addEventListener('click', event => {
  if (event.target === $('#cartOverlay')) closeCart();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeCart();
});

const checkoutOverlay = $('#checkoutOverlay');
const checkoutForm = $('#checkoutForm');

function closeCheckout() {
  checkoutOverlay.classList.remove('open');
  document.body.classList.remove('checkout-open');
}

function showCheckout() {
  if (!cart.length) return;
  closeCart();
  $('#checkoutItems').innerHTML = cart.map(item =>
    `<div class="checkout-item"><span>${item.name} × ${item.qty.toLocaleString('fa-IR')}</span><strong>${formatMoney(item.price * item.qty)}</strong></div>`
  ).join('');
  $('#checkoutTotal').textContent = formatMoney(
    cart.reduce((sum, item) => sum + item.price * item.qty, 0)
  );
  checkoutOverlay.classList.add('open');
  document.body.classList.add('checkout-open');
}

$('#checkoutBtn').addEventListener('click', showCheckout);
$('#closeCheckout').addEventListener('click', closeCheckout);
checkoutOverlay.addEventListener('click', event => {
  if (event.target === checkoutOverlay) closeCheckout();
});

checkoutForm.addEventListener('submit', event => {
  event.preventDefault();

  const data = new FormData(checkoutForm);
  const fullName = String(data.get('fullName') || '').trim();
  const mobile = normalizeDigits(data.get('mobile') || '').replace(/\s/g, '');
  const province = String(data.get('province') || '').trim();
  const city = String(data.get('city') || '').trim();
  const address = String(data.get('address') || '').trim();
  const postalCode = normalizeDigits(data.get('postalCode') || '').replace(/\s/g, '');
  const notes = String(data.get('notes') || '').trim();

  if (!/^09\d{9}$/.test(mobile)) {
    alert('شماره موبایل باید ۱۱ رقم و با ۰۹ شروع شود.');
    return;
  }
  if (!/^\d{10}$/.test(postalCode)) {
    alert('کد پستی باید دقیقاً ۱۰ رقم باشد.');
    return;
  }
  if (!cart.length) {
    alert('سبد خرید خالی است.');
    closeCheckout();
    return;
  }

  const total = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const itemLines = cart.map((item, index) =>
    `${index + 1}. ${item.name} | تعداد: ${item.qty} | مبلغ: ${formatMoney(item.price * item.qty)}`
    );

    const orderCode = 'DB-' + Date.now();

    const message = [
      '❄️ فروشگاه دکتر برودت',
      '━━━━━━━━━━━━━━━━━━',
      `🧾 سفارش جدید | ${orderCode}`,
      '━━━━━━━━━━━━━━━━━━',
      '',
      '👤 مشخصات خریدار',
      `نام: ${fullName}`,
      `موبایل: ${mobile}`,
      `استان: ${province}`,
      `شهر: ${city}`,
      `آدرس: ${address}`,
      `کد پستی: ${postalCode}`,
      '',
      '🛒 اقلام سفارش',
      ...itemLines,
      '',
      '━━━━━━━━━━━━━━━━━━',
      `💰 مبلغ نهایی: ${formatMoney(total)}`,
      `📝 توضیحات: ${notes || 'ندارد'}`,
      '━━━━━━━━━━━━━━━━━━',
      `کد پیگیری: ${orderCode}`
    ].join('\n');



  const whatsappUrl = 'https://wa.me/989197701790?text=' + encodeURIComponent(message);
  const whatsappWindow = window.open(whatsappUrl, '_blank');
  if (!whatsappWindow) window.location.href = whatsappUrl;
});

renderCart();

$$('.favorite').forEach(b=>b.onclick=()=>{
 b.classList.toggle('selected');
 b.innerHTML=b.classList.contains('selected')
 ?'<i class="fa-solid fa-heart"></i>'
 :'<i class="fa-regular fa-heart"></i>';
});

$$('.tabs button').forEach(b=>b.onclick=()=>{
 $$('.tabs button').forEach(x=>x.classList.remove('active'));
 b.classList.add('active');
});


$('#backTop').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});

/* DR BORUDAT - PANEL CONNECTED HOMEPAGE */
(() => {
  const featuredTrack = document.getElementById('featuredTrack');
  const latestTrack = document.getElementById('latestTrack');
  const bestTrack = document.getElementById('bestTrack');
  const categoryGrid = document.querySelector('.category-grid');
  const categoryFilter = document.getElementById('categoryFilter');
  const stockFilter = document.getElementById('stockFilter');
  const blogTrack = document.getElementById('blogTrack');

  if (!featuredTrack || !latestTrack || !bestTrack) return;

  let homepageProducts = [];
  let latestProducts = null;
  let panelCategories = null;
  let bestSections = {};
  let bestMode = 'bestseller';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[ch]);

  const latinDigits = value => String(value ?? '')
    .replace(/[\u06F0-\u06F9]/g, d => String(d.charCodeAt(0) - 0x06F0))
    .replace(/[\u0660-\u0669]/g, d => String(d.charCodeAt(0) - 0x0660))
    .replace(/[\u066C\u060C,]/g, '');

  const toman = value => {
    const n = Number(latinDigits(value));
    return Number.isFinite(n) && n > 0 ? n : 0;
  };

  const rialText = value =>
    Math.round(toman(value) * 10).toLocaleString('fa-IR') + ' ریال';

  const cleanText = value =>
    String(value ?? '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

  async function getApi(path) {
    const cacheKey = 'drbApi:' + path;
    let lastError;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(API_BASE + path, { cache: 'no-store' });
        if (!response.ok) throw new Error(path + ': HTTP ' + response.status);
        const data = await response.json();
        if (!data || data.success !== true) throw new Error(path + ': پاسخ نامعتبر');
        try { localStorage.setItem(cacheKey, JSON.stringify(data)); } catch (_) {}
        return data;
      } catch (error) {
        lastError = error;
        if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 2500 * (attempt + 1)));
      }
    }
    try {
      const saved = JSON.parse(localStorage.getItem(cacheKey) || 'null');
      if (saved && saved.success === true) return saved;
    } catch (_) {}
    throw lastError;
  }

  function productCard(product) {
    const name = esc(product.name);
    const image = backendMediaUrl(product.image);
    const price = toman(product.price);
    const stock = Number(latinDigits(product.stock)) || 0;
    const discount = Number(product.discount_percent) || 0;

    return `
      <article class="product-card"
        data-product-id="${esc(product.id)}"
        data-product-name="${name}"
        data-product-price="${price}"
        data-product-category="${esc(product.category)}"
        data-product-stock="${stock}">
        <div class="product-image">
          ${image
            ? `<img src="${esc(image)}" alt="${name}" loading="lazy"
                 onerror="this.remove();this.parentElement.classList.add('image-unavailable');this.parentElement.textContent='تصویر محصول در دسترس نیست';">`
            : `<div class="image-unavailable">تصویر محصول ثبت نشده است</div>`}
        </div>
        ${discount > 0
          ? `<span class="discount">${discount.toLocaleString('fa-IR')}٪ تخفیف</span>`
          : (product.is_special ? '<span class="discount">ویژه</span>' : '')}
        <div class="product-actions">
          <button type="button" class="add-cart" aria-label="افزودن به سبد خرید">
            <i class="fa-solid fa-cart-shopping"></i>
          </button>
          <button type="button" class="favorite" aria-label="افزودن به علاقه‌مندی">
            <i class="fa-regular fa-heart"></i>
          </button>
        </div>
        <h3>${name}</h3>
        <p class="price">${price ? rialText(price) : 'تماس بگیرید'}</p>
        ${stock > 0
          ? '<small class="product-stock">موجود</small>'
          : '<small class="product-stock out">ناموجود</small>'}
      </article>`;
  }

  function renderTrack(track, products, emptyMessage) {
    if (!track) return;
    if (!Array.isArray(products) || !products.length) {
      track.innerHTML = `<p class="homepage-empty">${esc(emptyMessage)}</p>`;
      return;
    }
    track.innerHTML = products.map(productCard).join('');
  }

  function renderLatest() {
    const category = categoryFilter?.value || '';
    const stock = stockFilter?.value || '';
    let items = [...(latestProducts || homepageProducts)];

    if (category) items = items.filter(p => String(p.category || '') === category);
    if (stock === 'yes') items = items.filter(p => Number(latinDigits(p.stock)) > 0);
    if (stock === 'no') items = items.filter(p => !(Number(latinDigits(p.stock)) > 0));

    renderTrack(latestTrack, items, 'محصولی با این مشخصات پیدا نشد.');
  }

  function renderBest() {
    const section = bestSections[bestMode];
    const messages = {
      bestseller: 'هنوز فروش تکمیل‌شده‌ای برای نمایش پرفروش‌ترین‌ها ثبت نشده است.',
      discounted: 'در حال حاضر محصول تخفیف‌داری برای نمایش وجود ندارد.',
      newest: 'هنوز محصولی برای نمایش ثبت نشده است.'
    };

    if (!section || section.active !== true) {
      renderTrack(bestTrack, [], 'این بخش در حال حاضر از پنل غیرفعال است.');
      return;
    }

    renderTrack(bestTrack, section.products || [], messages[bestMode] || messages.newest);
  }

  function renderCategories() {
    let categories = Array.isArray(panelCategories) ? panelCategories : [];

    if (!categories.length) {
      categories = [...new Set(
        homepageProducts.map(p => String(p.category || '').trim()).filter(Boolean)
      )].map(name => ({ name, image_url: '' }));
    }

    if (categoryFilter) {
      const selected = categoryFilter.value;
      categoryFilter.innerHTML =
        '<option value="">همه دسته‌بندی‌ها</option>' +
        categories.map(item =>
          `<option value="${esc(item.name)}">${esc(item.name)}</option>`
        ).join('');
      if (categories.some(item => item.name === selected)) {
        categoryFilter.value = selected;
      }
    }

    if (categoryGrid) {
      categoryGrid.innerHTML = categories.length
        ? categories.map(item => {
            const name = String(item.name || '');
            const image = backendMediaUrl(item.image_url);
            return `<a href="#latest" class="category-banner" data-home-category="${esc(name)}">
              ${image ? `<img src="${esc(image)}" alt="${esc(name)}" loading="lazy">` : ''}
              <div>
                <small>محصولات دکتر برودت</small>
                <h3>${esc(name)}</h3>
                <span>مشاهده محصولات</span>
              </div>
            </a>`;
          }).join('')
        : '<p class="homepage-empty">هنوز دسته‌بندی فعالی در پنل ثبت نشده است.</p>';
    }
  }

  function renderMagazine(posts) {
    if (!blogTrack) return;
    if (!Array.isArray(posts) || !posts.length) {
      blogTrack.innerHTML = '<p class="homepage-empty">هنوز مطلب منتشرشده‌ای در مجله ثبت نشده است.</p>';
      return;
    }

    blogTrack.innerHTML = posts.map(post => {
      const title = esc(post.title || 'مطلب مجله');
      const excerpt = esc(cleanText(post.excerpt || post.content).slice(0, 240));
      const content = esc(cleanText(post.content));
      const image = backendMediaUrl(post.image_url);
      let date = '';
      if (post.created_at) {
        const parsed = new Date(post.created_at);
        if (!Number.isNaN(parsed.getTime())) {
          date = parsed.toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' });
        }
      }

      return `<article class="blog-card">
        ${image ? `<img src="${esc(image)}" alt="${title}" loading="lazy">` : ''}
        ${date ? `<span class="date">${esc(date)}</span>` : ''}
        <label>مجله دکتر برودت</label>
        <h3>${title}</h3>
        <div class="blog-meta"><span>دکتر برودت</span></div>
        <p>${excerpt}</p>
        ${content && content !== cleanText(post.excerpt)
          ? `<details class="magazine-more"><summary>ادامه مطلب</summary><p>${content}</p></details>`
          : ''}
      </article>`;
    }).join('');
  }

  function updateBestTabs() {
    const tabValues = {
      popular: 'bestseller',
      bestseller: 'bestseller',
      discounted: 'discounted',
      newest: 'newest'
    };

    document.querySelectorAll('.tabs button').forEach(tab => {
      const key = tabValues[tab.dataset.tab] || tab.dataset.tab;
      tab.classList.toggle('active', key === bestMode);
    });
  }

  async function loadHomepage() {
    [featuredTrack, latestTrack, bestTrack].forEach(track => {
      track.innerHTML = '<p class="homepage-empty">در حال دریافت اطلاعات فروشگاه...</p>';
    });

    const paths = [
      '/api/products',
      '/api/categories',
      '/api/latest-products',
      '/api/store-best',
      '/api/slides',
      '/api/magazine'
    ];

    const results = await Promise.allSettled(paths.map(getApi));

    if (results[0].status !== 'fulfilled' ||
        !Array.isArray(results[0].value.products)) {
      console.error('Homepage products API:', results[0].reason);
      [featuredTrack, latestTrack, bestTrack].forEach(track => {
        track.innerHTML = '<p class="homepage-empty">دریافت محصولات از سرور انجام نشد. اتصال پنل را بررسی کنید.</p>';
      });
      return;
    }

    const productsData = results[0].value;
    homepageProducts = productsData.products.filter(p =>
      p && p.id != null && String(p.name || '').trim()
    );

    renderTrack(
      featuredTrack,
      homepageProducts.filter(p =>
        p.is_special === true || p.is_special === 1 || p.is_special === 'true'
      ),
      'هنوز محصول ویژه‌ای از پنل انتخاب نشده است.'
    );

    if (results[1].status === 'fulfilled' &&
        Array.isArray(results[1].value.categories)) {
      panelCategories = results[1].value.categories;
    }

    if (results[2].status === 'fulfilled' &&
        Array.isArray(results[2].value.products)) {
      latestProducts = results[2].value.products;
    }

    if (results[3].status === 'fulfilled' &&
        results[3].value.sections) {
      bestSections = results[3].value.sections;
    } else {
      console.warn('Store-best API is not available yet:', results[3].reason);
    }

    if (results[4].status === 'fulfilled' &&
        Array.isArray(results[4].value.slides)) {
      renderPanelSlides(results[4].value.slides);
    }

    if (results[5].status === 'fulfilled' &&
        Array.isArray(results[5].value.posts)) {
      renderMagazine(results[5].value.posts);
    } else {
      console.warn('Magazine API is not available yet:', results[5].reason);
    }

    renderCategories();
    renderLatest();
    updateBestTabs();
    renderBest();
  }

  document.addEventListener('click', event => {
    const addButton = event.target.closest('.add-cart');
    if (addButton) {
      const card = addButton.closest('.product-card');
      if (!card) return;

      event.preventDefault();
      event.stopPropagation();

      const name = card.dataset.productName || '';
      const price = toman(card.dataset.productPrice);

      if (!name || !price) {
        alert('قیمت این محصول در پنل ثبت نشده است.');
        return;
      }

      const existing = cart.find(item =>
        item.name === name && item.price === price
      );

      if (existing) existing.qty += 1;
      else cart.push({ name, price, qty: 1 });

      saveCart();
      renderCart();
      return;
    }

    const categoryLink = event.target.closest('[data-home-category]');
    if (categoryLink) {
      const category = categoryLink.dataset.homeCategory;
      if (categoryFilter) categoryFilter.value = category;
      renderLatest();
    }
  });

  document.addEventListener('click', event => {
    const tab = event.target.closest('.tabs button');
    if (!tab) return;

    const map = {
      popular: 'bestseller',
      bestseller: 'bestseller',
      discounted: 'discounted',
      newest: 'newest'
    };

    bestMode = map[tab.dataset.tab] || 'bestseller';
    updateBestTabs();
    renderBest();
  });

  categoryFilter?.addEventListener('change', renderLatest);
  stockFilter?.addEventListener('change', renderLatest);

  document.getElementById('filterBtn')?.addEventListener('click', event => {
    event.preventDefault();
    renderLatest();
    document.getElementById('latest')?.scrollIntoView({ behavior: 'smooth' });
  });

  loadHomepage();
})();
