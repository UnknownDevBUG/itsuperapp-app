import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/pages/Login.vue"),
  },
  {
    path: "/",
    name: "Home",
    component: () => import("@/pages/Home.vue"),
  },
];

const router = createRouter({
  history: createWebHistory("/frontend"),
  routes,
});

export default router;
