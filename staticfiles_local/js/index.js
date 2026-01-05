// ===== VIDEO CONFIGURATION =====
// Define your video list here — add or remove items as needed
const VIDEOS = [
  {
    id: "1vDueYiSXyk", // Your YouTube Shorts ID
    title: "Getting Started with ChamaSpace",
    thumbnail: "https://img.youtube.com/vi/1vDueYiSXyk/maxresdefault.jpg"
  },
  // Add more videos like this if needed:
  // {
  //   id: "mEoBwBACmXs",
  //   title: "Managing Your Chama",
  //   thumbnail: "https://img.youtube.com/vi/mEoBwBACmXs/maxresdefault.jpg"
  // }
];

// ===== DOM READY EVENT =====
document.addEventListener("DOMContentLoaded", () => {
  // Render videos dynamically
  renderVideos();

  // Animate hero & signup sections
  const elements = document.querySelectorAll(".hero-section > *, .signup-section > *");
  elements.forEach((element, index) => {
    element.style.opacity = "0";
    element.style.transform = "translateY(20px)";
    element.style.transition = "all 0.6s ease";

    setTimeout(() => {
      element.style.opacity = "1";
      element.style.transform = "translateY(0)";
    }, index * 100);
  });

  // Animate video items
  const videoItems = document.querySelectorAll(".video-item");
  videoItems.forEach((item, index) => {
    item.style.opacity = "0";
    item.style.transform = "translateY(30px)";
    item.style.transition = "all 0.6s ease";

    setTimeout(() => {
      item.style.opacity = "1";
      item.style.transform = "translateY(0)";
    }, 300 + index * 150);
  });
});

// ===== RENDER VIDEOS DYNAMICALLY =====
function renderVideos() {
  const videoGrid = document.getElementById("videoGrid");
  const template = document.getElementById("videoItemTemplate");

  // Clear any existing content
  videoGrid.innerHTML = "";

  // Create and append each video item
  VIDEOS.forEach(video => {
    const clone = template.content.cloneNode(true);
    const item = clone.querySelector(".video-item");
    const img = clone.querySelector("img");
    const p = clone.querySelector("p");

    item.dataset.videoId = video.id;
    img.src = video.thumbnail;
    p.textContent = video.title;

    // Attach click handler
    item.addEventListener("click", () => openVideoModal(video.id));

    videoGrid.appendChild(clone);
  });

  // Optional: Hide the entire video section if no videos exist
  if (VIDEOS.length === 0) {
    videoGrid.parentElement.style.display = "none";
  }
}

// ===== VIDEO MODAL FUNCTIONS =====
function openVideoModal(videoId) {
  const modal = document.getElementById("videoModal");
  const videoFrame = document.getElementById("videoFrame");

  // Construct YouTube embed URL
  // Use 'autoplay=1' and 'modestbranding=1' for cleaner experience
  const videoUrl = `https://www.youtube.com/embed/${videoId}?autoplay=1&modestbranding=1`;

  videoFrame.src = videoUrl;
  // Set the video id on modal content for CSS that targets vertical videos
  const modalContent = document.getElementById("modalContent");
  if (modalContent) {
    modalContent.setAttribute("data-video-id", videoId);
  }
  modal.style.display = "block";
  document.body.style.overflow = "hidden";
}

function closeVideoModal() {
  const modal = document.getElementById("videoModal");
  const videoFrame = document.getElementById("videoFrame");

  videoFrame.src = "";
  modal.style.display = "none";
  document.body.style.overflow = "auto";
}

// Close modal when clicking outside
window.onclick = (event) => {
  const modal = document.getElementById("videoModal");
  if (event.target === modal) {
    closeVideoModal();
  }
};

// Close modal with Escape key
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeVideoModal();
  }
});