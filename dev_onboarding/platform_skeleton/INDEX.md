# Platform Skeleton - Documentation Index

Quick reference guide to all skeleton documentation.

## 📚 Documentation Files

### Getting Started

1. **[README.md](./README.md)** - Start here!
   - Overview and purpose
   - Quick start guide
   - Directory structure overview
   - Customization checklist

2. **[SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)** - Step-by-step setup
   - Prerequisites
   - Environment configuration
   - Database initialization
   - Service startup
   - Verification steps

3. **[COPY_CHECKLIST.md](./COPY_CHECKLIST.md)** - What to copy from eliza-platform
   - Required files list
   - Copy process
   - Verification checklist

### Customization Guides

4. **[NAVIGATION_GUIDE.md](./NAVIGATION_GUIDE.md)** - Navigation customization
   - Navigation structure
   - How to add features
   - Available icons
   - Permission setup
   - Design consistency

5. **[CRITICAL_PATTERNS.md](./CRITICAL_PATTERNS.md)** - Required patterns
   - Database session management
   - Multi-tenancy
   - API routes
   - Celery tasks
   - Frontend components
   - Common mistakes

### Reference

6. **[DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md)** - Complete structure
   - Full directory tree
   - File naming conventions
   - Critical directories
   - Optional directories

## 🎯 Quick Navigation

### I want to...

**...get started quickly**
→ Read [README.md](./README.md) → Follow [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)

**...understand what to copy**
→ Read [COPY_CHECKLIST.md](./COPY_CHECKLIST.md)

**...customize the navigation**
→ Read [NAVIGATION_GUIDE.md](./NAVIGATION_GUIDE.md)

**...understand critical patterns**
→ Read [CRITICAL_PATTERNS.md](./CRITICAL_PATTERNS.md)

**...see the full structure**
→ Read [DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md)

**...troubleshoot setup**
→ Check [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md) → Common Issues section

## 📋 Typical Workflow

1. **Initial Setup** (Day 1)
   - Read [README.md](./README.md)
   - Follow [COPY_CHECKLIST.md](./COPY_CHECKLIST.md) to copy files
   - Follow [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md) to get running

2. **Customization** (Day 2-3)
   - Read [NAVIGATION_GUIDE.md](./NAVIGATION_GUIDE.md)
   - Customize navigation for your features
   - Review [CRITICAL_PATTERNS.md](./CRITICAL_PATTERNS.md)

3. **Feature Development** (Ongoing)
   - Reference [CRITICAL_PATTERNS.md](./CRITICAL_PATTERNS.md) for patterns
   - Use [DIRECTORY_STRUCTURE.md](./DIRECTORY_STRUCTURE.md) for structure
   - Follow established patterns

## 🔑 Key Concepts

### Platform vs. Products
- **Platform**: Core infrastructure (databases, auth, API structure)
- **Products**: Features built on platform (your custom features)

### Critical Components
1. **Navigation** - Must maintain consistent structure
2. **Database Sessions** - Never store in state
3. **Multi-Tenancy** - Always filter by `customer_id`
4. **Container Rebuilds** - Always rebuild after code changes

### Design Consistency
- Navigation width: `w-60` expanded, `w-16` collapsed
- Section headers: Uppercase, consistent styling
- Icons: Heroicons, consistent sizing

## ⚠️ Common Pitfalls

1. **Not rebuilding containers** after code changes
2. **Storing database sessions** in flow state
3. **Forgetting customer_id** filtering
4. **Changing navigation structure** inconsistently
5. **Skipping permission checks** in navigation

## 📞 Getting Help

If you're stuck:

1. Check relevant documentation file
2. Review [CRITICAL_PATTERNS.md](./CRITICAL_PATTERNS.md) for common mistakes
3. Check [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md) troubleshooting section
4. Review main platform documentation:
   - [Main Onboarding Guide](../README.md)
   - [Engineering Tasks](../ENGINEERING_TASKS.md)
   - [Cookbook](../../cookbook/README.md)

## ✅ Success Checklist

You'll know the skeleton is set up correctly when:

- [ ] All Docker services start successfully
- [ ] Database migrations run without errors
- [ ] API docs accessible at `http://localhost:5001/docs`
- [ ] Frontend loads at `http://localhost:3000`
- [ ] Navigation displays correctly
- [ ] Authentication flow works
- [ ] You can add new routes and they appear in navigation

---

**Remember**: This skeleton provides the foundation. Build your features on top using established patterns. The goal is to validate and improve platform patterns through real usage.

