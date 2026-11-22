const $=s=>document.querySelector(s);
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
const slides = [...document.querySelectorAll('.hero-slide')];
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

$('#filterBtn').onclick=()=>{
 const category=$('#categoryFilter').value;
 const stock=$('#stockFilter').value;
 alert('فیلتر انتخاب شد: '+(category||'همه دسته‌ها')+' | '+(stock||'همه وضعیت‌ها'));
};

$('#backTop').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});

/* DR BORUDAT - LIVE HOMEPAGE PRODUCTS */
(() => {
  const API = '/api/products';
  const featuredTrack = document.getElementById('featuredTrack');
  const latestTrack = document.getElementById('latestTrack');
  const bestTrack = document.getElementById('bestTrack');
  const categoryGrid = document.querySelector('.category-grid');
  const categoryFilter = document.getElementById('categoryFilter');
  const stockFilter = document.getElementById('stockFilter');

  if (!featuredTrack || !latestTrack || !bestTrack) return;

  let homepageProducts = [];
  let bestMode = 'popular';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;',
    '"': '&quot;', "'": '&#39;'
  })[ch]);

  const toman = value => {
    const n = Number(String(value ?? '').replace(/,/g, ''));
    return Number.isFinite(n) && n > 0 ? n : 0;
  };

  const rialText = value =>
    Math.round(toman(value) * 10).toLocaleString('fa-IR') + ' ریال';

  const imageUrl = value => {
    const raw = String(value || '').trim();
    if (!raw) return '';
    try {
      const url = new URL(raw, window.location.origin);
      return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
    } catch (_) {
      return '';
    }
  };

  function productCard(product) {
    const name = esc(product.name);
    const image = imageUrl(product.image);
    const price = toman(product.price);
    const stock = Number(product.stock) || 0;

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
        ${product.is_special ? '<span class="discount">ویژه</span>' : ''}
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
          ? `<small class="product-stock">موجود</small>`
          : `<small class="product-stock">ناموجود</small>`}
      </article>`;
  }

  function renderTrack(track, products, emptyMessage) {
    if (!products.length) {
      track.innerHTML = `<p class="homepage-empty">${esc(emptyMessage)}</p>`;
      return;
    }
    track.innerHTML = products.map(productCard).join('');
  }

  function renderLatest() {
    const category = categoryFilter?.value || '';
    const stock = stockFilter?.value || '';

    let items = [...homepageProducts];

    if (category) items = items.filter(p => p.category === category);
    if (stock === 'yes') items = items.filter(p => Number(p.stock) > 0);
    if (stock === 'no') items = items.filter(p => Number(p.stock) <= 0);

    renderTrack(
      latestTrack,
      items.slice(0, 16),
      'محصولی با این مشخصات پیدا نشد.'
    );
  }

  function renderBest() {
    let items = [...homepageProducts];

    if (bestMode === 'newest') {
      items.sort((a, b) =>
        new Date(b.created_at || 0) - new Date(a.created_at || 0)
      );
    } else if (bestMode === 'popular') {
      items = items.filter(p => Number(p.sales_count) > 0)
        .sort((a, b) => Number(b.sales_count) - Number(a.sales_count));
    } else if (bestMode === 'discounted') {
      items = items.filter(p => Number(p.discount_percent) > 0)
        .sort((a, b) => Number(b.discount_percent) - Number(a.discount_percent));
    }

    const message = bestMode === 'popular'
      ? 'هنوز اطلاعات فروش محصولات ثبت نشده است.'
      : bestMode === 'discounted'
        ? 'در حال حاضر محصول تخفیف‌دار ثبت نشده است.'
        : 'هنوز محصولی ثبت نشده است.';

    renderTrack(bestTrack, items.slice(0, 16), message);
  }

  function renderCategories() {
    const categories = [...new Set(
      homepageProducts.map(p => p.category).filter(Boolean)
    )];

    if (categoryFilter) {
      const selected = categoryFilter.value;
      categoryFilter.innerHTML =
        '<option value="">همه دسته‌بندی‌ها</option>' +
        categories.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
      if (categories.includes(selected)) categoryFilter.value = selected;
    }

    if (categoryGrid) {
      categoryGrid.innerHTML = categories.length
        ? categories.map(category => `
            <a href="#latest" class="category-banner"
               data-home-category="${esc(category)}">
              <div>
                <small>محصولات دکتر برودت</small>
                <h3>${esc(category)}</h3>
                <span>مشاهده محصولات</span>
              </div>
            </a>`).join('')
        : '<p class="homepage-empty">هنوز دسته‌بندی محصولی ثبت نشده است.</p>';
    }
  }

  async function loadHomepageProducts() {
    featuredTrack.innerHTML = '<p class="homepage-empty">در حال دریافت محصولات...</p>';
    latestTrack.innerHTML = '<p class="homepage-empty">در حال دریافت محصولات...</p>';
    bestTrack.innerHTML = '<p class="homepage-empty">در حال دریافت محصولات...</p>';

    try {
      const response = await fetch(API, { cache: 'no-store' });
      if (!response.ok) throw new Error('HTTP ' + response.status);

      const data = await response.json();
      if (!data || data.success !== true || !Array.isArray(data.products)) {
        throw new Error('پاسخ نامعتبر از سرور محصولات');
      }

      homepageProducts = data.products.filter(p =>
        p && p.id != null && String(p.name || '').trim()
      );

      renderTrack(
        featuredTrack,
        homepageProducts.filter(p =>
          p.is_special === true || p.is_special === 1 || p.is_special === 'true'
        ),
        'هنوز محصول ویژه‌ای از پنل انتخاب نشده است.'
      );

      renderCategories();
      renderLatest();
      renderBest();

    } catch (error) {
      console.error('Homepage products:', error);
      const message = 'دریافت محصولات از سرور انجام نشد. اتصال پنل را بررسی کنید.';
      [featuredTrack, latestTrack, bestTrack].forEach(track => {
        track.innerHTML = `<p class="homepage-empty">${message}</p>`;
      });
    }
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
    bestMode = tab.dataset.tab || 'popular';
    renderBest();
  });

  categoryFilter?.addEventListener('change', renderLatest);
  stockFilter?.addEventListener('change', renderLatest);

  document.getElementById('filterBtn')?.addEventListener('click', event => {
    event.preventDefault();
    renderLatest();
    document.getElementById('latest')?.scrollIntoView({ behavior: 'smooth' });
  });

  loadHomepageProducts();
})();
